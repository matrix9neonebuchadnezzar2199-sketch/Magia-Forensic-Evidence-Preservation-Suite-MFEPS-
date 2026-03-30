"""
MFEPS v2.0 — イメージング統合サービス
UIとイメージングエンジンを仲介するオーケストレータ
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Callable

from src.core.imaging_engine import ImagingEngine, ImagingJobParams, ImagingResult
from src.core.device_detector import DeviceInfo
from src.core.write_blocker import check_write_protection
from src.models.database import get_session
from src.models.schema import ImagingJob, HashRecord, ChainOfCustody, AuditLog
from src.utils.config import get_config

logger = logging.getLogger("mfeps.imaging_service")


class ImagingService:
    """イメージングオーケストレータ"""

    def __init__(self):
        self._engines: dict[str, ImagingEngine] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._results: dict[str, dict] = {}
        self._job_actors: dict[str, str] = {}


    async def start_imaging(
        self,
        device: DeviceInfo,
        case_id: str,
        evidence_id: str,
        output_format: str = "raw",
        verify: bool = True,
        progress_callback: Optional[Callable] = None,
        actor_name: str = "MFEPS Auto",
    ) -> str:
        """
        イメージングを開始。
        Returns: job_id
        """
        config = get_config()
        job_id = str(uuid.uuid4())

        from src.services.case_service import CaseService, EvidenceService
        case_svc = CaseService()
        ev_svc = EvidenceService()
        
        real_case_id = case_svc.get_or_create_case(case_number=case_id)
        real_evidence_id = ev_svc.get_or_create_evidence(
            case_id=real_case_id,
            evidence_number=evidence_id,
            media_type="usb_hdd",
            device_model=device.model,
            device_serial=device.serial,
            capacity_bytes=device.capacity_bytes
        )

        # 出力先ディレクトリ (ディレクトリ名にはユーザーが入力したわかりやすい文字列番号を使う)
        output_dir = config.output_dir / case_id / evidence_id
        output_dir.mkdir(parents=True, exist_ok=True)

        wb_status = check_write_protection(device.device_path)
        if wb_status["hardware_blocked"] and wb_status["registry_blocked"]:
            write_block_method = "both"
        elif wb_status["hardware_blocked"]:
            write_block_method = "hardware"
        elif wb_status["registry_blocked"]:
            write_block_method = "software"
        else:
            write_block_method = "none"

        # DB レコード作成
        session = get_session()
        try:
            db_job = ImagingJob(
                id=job_id,
                evidence_id=real_evidence_id,
                status="pending",
                source_path=device.device_path,
                output_path=str(output_dir / "image.dd"),
                output_format=output_format,
                total_bytes=device.capacity_bytes,
                buffer_size=config.mfeps_buffer_size,
                write_block_method=write_block_method,
            )
            session.add(db_job)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"DB レコード作成失敗: {e}")
            raise
        finally:
            session.close()

        # エンジン作成
        self._job_actors[job_id] = actor_name
        engine = ImagingEngine(buffer_size=config.mfeps_buffer_size)
        if progress_callback:
            engine.set_progress_callback(progress_callback)
        self._engines[job_id] = engine

        # ジョブパラメータ
        job_params = ImagingJobParams(
            job_id=job_id,
            evidence_id=real_evidence_id,
            case_id=real_case_id,
            source_path=device.device_path,
            output_dir=str(output_dir),
            output_format=output_format,
            buffer_size=config.mfeps_buffer_size,
            verify_after_copy=verify,
        )

        # 非同期タスク起動
        task = asyncio.create_task(self._run_imaging(job_id, engine, job_params))
        self._tasks[job_id] = task

        logger.info(f"イメージングジョブ開始: {job_id}")
        return job_id

    async def _run_imaging(
        self, job_id: str, engine: ImagingEngine, params: ImagingJobParams
    ) -> None:
        """イメージング実行 + DB更新"""
        # ステータス更新 → imaging
        self._update_job_status(job_id, "imaging",
                                started_at=datetime.now(timezone.utc))

        try:
            result = await engine.execute(params)
            await self.on_imaging_complete(result)
        except Exception as e:
            logger.error(f"イメージングタスクエラー: {e}")
            self._job_actors.pop(job_id, None)
            self._update_job_status(job_id, "failed")
            self._results[job_id] = {
                "status": "failed",
                "error_message": str(e),
            }
        finally:
            self._engines.pop(job_id, None)
            self._tasks.pop(job_id, None)


    async def on_imaging_complete(self, result: ImagingResult) -> None:
        """イメージング完了処理: DB更新"""
        actor_name = self._job_actors.pop(result.job_id, "MFEPS Auto")
        session = get_session()
        try:
            # imaging_jobs 更新
            job = session.query(ImagingJob).get(result.job_id)
            if job:
                job.status = result.status
                job.copied_bytes = result.copied_bytes
                job.error_count = result.error_count
                job.completed_at = datetime.now(timezone.utc)
                job.elapsed_seconds = result.elapsed_seconds
                job.avg_speed_mbps = result.avg_speed_mibps
                if result.output_path:
                    job.output_path = result.output_path

            # ソースハッシュ記録
            if result.source_hashes:
                source_hash = HashRecord(
                    job_id=result.job_id,
                    target="source",
                    md5=result.source_hashes.get("md5", ""),
                    sha1=result.source_hashes.get("sha1", ""),
                    sha256=result.source_hashes.get("sha256", ""),
                    match_result="pending",
                )
                session.add(source_hash)

            # 検証ハッシュ記録
            if result.verify_hashes:
                verify_hash = HashRecord(
                    job_id=result.job_id,
                    target="verify",
                    md5=result.verify_hashes.get("md5", ""),
                    sha1=result.verify_hashes.get("sha1", ""),
                    sha256=result.verify_hashes.get("sha256", ""),
                    match_result=result.match_result,
                )
                session.add(verify_hash)

            # CoC エントリ追加
            if job:
                coc = ChainOfCustody(
                    evidence_id=job.evidence_id,
                    action="imaged",
                    actor_name=actor_name,
                    description=f"イメージング {result.status}: "
                                f"{result.copied_bytes} bytes, "
                                f"{result.elapsed_seconds}s",
                    hash_snapshot=str(result.source_hashes),
                )
                session.add(coc)

            session.commit()
            logger.info(f"DB更新完了: job_id={result.job_id}")

        except Exception as e:
            session.rollback()
            logger.error(f"DB更新失敗: {e}")
        finally:
            session.close()

        # 結果をキャッシュ（UI参照用）
        self._results[result.job_id] = {
            "status": result.status,
            "source_hashes": result.source_hashes,
            "verify_hashes": result.verify_hashes,
            "match_result": result.match_result,
            "total_bytes": result.total_bytes,
            "copied_bytes": result.copied_bytes,
            "error_count": result.error_count,
            "elapsed_seconds": result.elapsed_seconds,
            "avg_speed_mibps": result.avg_speed_mibps,
            "output_path": result.output_path,
        }

    def get_progress(self, job_id: str) -> dict:
        """実行中ジョブの進捗を取得"""
        engine = self._engines.get(job_id)
        if engine:
            return engine.get_progress()
        # エンジン削除後はキャッシュから返す
        if job_id in self._results:
            return self._results[job_id]
        return {"status": "unknown"}


    async def cancel_imaging(self, job_id: str) -> None:
        """イメージングをキャンセル"""
        engine = self._engines.get(job_id)
        if engine:
            await engine.cancel()
            self._update_job_status(job_id, "cancelled")

    async def pause_imaging(self, job_id: str) -> None:
        """一時停止"""
        engine = self._engines.get(job_id)
        if engine:
            await engine.pause()

    async def resume_imaging(self, job_id: str) -> None:
        """再開"""
        engine = self._engines.get(job_id)
        if engine:
            await engine.resume()

    def _update_job_status(self, job_id: str, status: str, **kwargs) -> None:
        """DBジョブステータス更新"""
        session = get_session()
        try:
            job = session.query(ImagingJob).get(job_id)
            if job:
                job.status = status
                for k, v in kwargs.items():
                    setattr(job, k, v)
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"ジョブステータス更新失敗: {e}")
        finally:
            session.close()


# シングルトン
_imaging_service: Optional[ImagingService] = None


def get_imaging_service() -> ImagingService:
    global _imaging_service
    if _imaging_service is None:
        _imaging_service = ImagingService()
    return _imaging_service
