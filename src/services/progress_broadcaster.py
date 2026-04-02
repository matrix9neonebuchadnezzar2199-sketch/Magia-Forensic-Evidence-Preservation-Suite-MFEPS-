"""
MFEPS v2.1.0 — 進捗ブロードキャスター (async push + 最新キャッシュ)
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("mfeps.progress_broadcaster")


class ProgressBroadcaster:
    """
    ジョブ進捗を購読者 Queue に配信し、最新値をキャッシュする。
    UI は get_latest でポーリングフォールバック可能。
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, asyncio.Queue] = {}
        self._latest: dict[str, dict] = {}

    def subscribe(self, client_id: str) -> asyncio.Queue:
        """クライアントを登録し、受信用 Queue を返す。"""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers[client_id] = q
        logger.debug("進捗購読: client=%s (total=%d)", client_id, len(self._subscribers))
        return q

    def unsubscribe(self, client_id: str) -> None:
        """クライアント登録を解除。"""
        self._subscribers.pop(client_id, None)
        logger.debug("進捗購読解除: client=%s", client_id)

    async def publish(self, job_id: str, progress: dict) -> None:
        """
        進捗を全購読者に配信。
        Queue が満杯のクライアントは古いメッセージを破棄。
        """
        self._latest[job_id] = progress
        msg = {"job_id": job_id, **progress}

        dead_clients: list[str] = []
        for cid, q in self._subscribers.items():
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(msg)
                except Exception:
                    dead_clients.append(cid)

        for cid in dead_clients:
            self.unsubscribe(cid)

    def get_latest(self, job_id: str) -> Optional[dict]:
        """最新の進捗を取得（ポーリングフォールバック用）。"""
        return self._latest.get(job_id)

    def clear_job(self, job_id: str) -> None:
        """完了ジョブの進捗キャッシュを除去。"""
        self._latest.pop(job_id, None)


_broadcaster: Optional[ProgressBroadcaster] = None


def get_broadcaster() -> ProgressBroadcaster:
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = ProgressBroadcaster()
    return _broadcaster


def reset_broadcaster_for_tests() -> None:
    """単体テスト用"""
    global _broadcaster
    _broadcaster = None
