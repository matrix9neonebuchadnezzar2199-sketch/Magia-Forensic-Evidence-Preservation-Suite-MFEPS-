"""
MFEPS v2.1.0 — ジョブキュー（Semaphore / PriorityQueue ベース並列制御）
"""
import asyncio
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger("mfeps.job_queue")


class JobPriority(int, Enum):
    HIGH = 0
    NORMAL = 1
    LOW = 2


class QueuedJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueuedJob:
    job_id: str
    coroutine_factory: Callable[[], Coroutine[Any, Any, None]]
    priority: JobPriority = JobPriority.NORMAL
    status: QueuedJobStatus = QueuedJobStatus.QUEUED
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    task: Optional[asyncio.Task] = None  # submit が返す完了待ち Task
    _exec_task: Optional[asyncio.Task] = None  # coroutine_factory 実行中
    done_event: asyncio.Event = field(default_factory=asyncio.Event)
    cancel_requested: bool = False


class JobQueue:
    """
    asyncio.PriorityQueue + ワーカーで同時実行数を制限し、優先度順に実行する。

    デフォルト max_concurrent=2:
      - USB/HDD と光学を同時に 1 つずつ、あるいは USB 2 台並列まで許可
      - 3 つ目以降はキュー待ち
    """

    def __init__(self, max_concurrent: int = 2):
        self._max_concurrent = max_concurrent
        self._pq: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._jobs: OrderedDict[str, QueuedJob] = OrderedDict()
        self._lock = asyncio.Lock()
        self._seq = 0
        self._workers_started = False
        self._worker_tasks: list[asyncio.Task] = []

    async def aclose(self) -> None:
        """テスト用: ワーカータスクを停止。"""
        for t in self._worker_tasks:
            t.cancel()
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()
        self._workers_started = False

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    @property
    def queue_size(self) -> int:
        return sum(
            1 for j in self._jobs.values()
            if j.status == QueuedJobStatus.QUEUED
        )

    @property
    def running_count(self) -> int:
        return sum(
            1 for j in self._jobs.values()
            if j.status == QueuedJobStatus.RUNNING
        )

    async def _ensure_workers(self) -> None:
        if self._workers_started:
            return
        self._workers_started = True
        for _ in range(self._max_concurrent):
            self._worker_tasks.append(asyncio.create_task(self._worker_loop()))

    async def _worker_loop(self) -> None:
        while True:
            try:
                _, __, qj = await self._pq.get()
            except asyncio.CancelledError:
                raise
            if qj.cancel_requested:
                qj.status = QueuedJobStatus.CANCELLED
                qj.completed_at = datetime.now(timezone.utc)
                qj.done_event.set()
                continue
            qj.status = QueuedJobStatus.RUNNING
            qj.started_at = datetime.now(timezone.utc)
            logger.info("ジョブ %s 開始", qj.job_id)
            exec_task = asyncio.create_task(qj.coroutine_factory())
            qj._exec_task = exec_task
            try:
                await exec_task
                if qj.status == QueuedJobStatus.RUNNING:
                    qj.status = QueuedJobStatus.COMPLETED
            except asyncio.CancelledError:
                qj.status = QueuedJobStatus.CANCELLED
                logger.info("ジョブ %s キャンセル", qj.job_id)
            except Exception as e:
                qj.status = QueuedJobStatus.FAILED
                qj.error_message = str(e)
                logger.error("ジョブ %s 失敗: %s", qj.job_id, e)
            finally:
                qj.completed_at = datetime.now(timezone.utc)
                qj.done_event.set()

    async def submit(
        self,
        job_id: str,
        coroutine_factory: Callable[[], Coroutine[Any, Any, None]],
        priority: JobPriority = JobPriority.NORMAL,
    ) -> tuple[str, asyncio.Task]:
        """ジョブをキューに投入。完了まで待機する Task を返す。"""
        queued_job = QueuedJob(
            job_id=job_id,
            coroutine_factory=coroutine_factory,
            priority=priority,
        )
        async with self._lock:
            self._jobs[job_id] = queued_job

        await self._ensure_workers()
        self._seq += 1
        await self._pq.put((priority.value, self._seq, queued_job))

        wait_task = asyncio.create_task(self._wait_until_done(queued_job))
        queued_job.task = wait_task
        logger.info(
            "ジョブ %s をキューに投入 (priority=%s, queue=%d, running=%d)",
            job_id, priority.name, self.queue_size, self.running_count,
        )
        return job_id, wait_task

    async def _wait_until_done(self, qj: QueuedJob) -> None:
        await qj.done_event.wait()

    async def cancel_job(self, job_id: str) -> bool:
        """キュー内または実行中のジョブをキャンセル。"""
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.cancel_requested = True
        if job._exec_task and not job._exec_task.done():
            job._exec_task.cancel()
        if job.task and not job.task.done():
            job.task.cancel()
        return True

    def get_status(self, job_id: str) -> Optional[dict]:
        """ジョブの状態を返す。"""
        job = self._jobs.get(job_id)
        if not job:
            return None
        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "priority": job.priority.name,
            "queued_at": job.queued_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
        }

    def list_jobs(self, limit: int = 50) -> list[dict]:
        """全ジョブ一覧。"""
        result: list[dict] = []
        for job in list(self._jobs.values())[-limit:]:
            st = self.get_status(job.job_id)
            if st:
                result.append(st)
        return result

    async def cleanup_completed(self, max_age_seconds: int = 3600) -> int:
        """完了済みジョブを辞書から除去。"""
        now = datetime.now(timezone.utc)
        to_remove: list[str] = []
        for jid, job in self._jobs.items():
            if job.status in (
                QueuedJobStatus.COMPLETED,
                QueuedJobStatus.FAILED,
                QueuedJobStatus.CANCELLED,
            ):
                if job.completed_at:
                    age = (now - job.completed_at).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(jid)
        async with self._lock:
            for jid in to_remove:
                del self._jobs[jid]
        return len(to_remove)


_job_queue: Optional[JobQueue] = None
_jq_lock = threading.Lock()


def get_job_queue(max_concurrent: int = 2) -> JobQueue:
    global _job_queue
    if _job_queue is not None:
        return _job_queue
    with _jq_lock:
        if _job_queue is None:
            _job_queue = JobQueue(max_concurrent=max_concurrent)
    return _job_queue


def reset_job_queue_for_tests() -> None:
    """単体テスト用: シングルトンをクリア（本番では呼ばない）。"""
    global _job_queue
    with _jq_lock:
        _job_queue = None
