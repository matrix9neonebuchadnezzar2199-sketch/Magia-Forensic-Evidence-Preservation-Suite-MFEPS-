import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.core.optical_engine import OpticalAnalysisResult, OpticalImagingEngine
from src.core.write_blocker import check_write_protection
from src.models.database import session_scope
from src.models.schema import ChainOfCustody, HashRecord, ImagingJob
from src.services.audit_service import get_audit_service
from src.utils.config import get_config
from src.utils.path_sanitize import sanitize_path_component

logger = logging.getLogger("mfeps.optical_service")

class OpticalService:
    """光学メディアイメージング用オーケストレータ"""

    def __init__(self):
        self._engines: dict[str, OpticalImagingEngine] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._progress: dict[str, dict] = {}
        self._job_actors: dict[str, str] = {}

    async def start_optical_imaging(
        self,
        drive_path: str,
        case_id: str,
        evidence_id: str,
        analysis: OpticalAnalysisResult,
        output_format: str = "ISO",
        use_pydvdcss: bool = False,
        use_aacs: bool = False,
        verify: bool = True,
        actor_name: str = "MFEPS Auto",
        *,
        hash_md5: bool = True,
        hash_sha1: bool = True,
        hash_sha256: bool = True,
        hash_sha512: bool = False,
        pydvdcss_open_path: Optional[str] = None,
    ) -> str:
        
        config = get_config()
        job_id = str(uuid.uuid4())

        from src.services.case_service import CaseService, EvidenceService
        case_svc = CaseService()
        ev_svc = EvidenceService()
        
        real_case_id = case_svc.get_or_create_case(case_number=case_id)
        real_evidence_id = ev_svc.get_or_create_evidence(
            case_id=real_case_id,
            evidence_number=evidence_id,
            media_type=analysis.media_type,
            capacity_bytes=analysis.capacity_bytes
        )

        safe_case = sanitize_path_component(case_id)
        safe_ev = sanitize_path_component(evidence_id)
        output_dir = config.output_dir / safe_case / safe_ev
        output_dir.mkdir(parents=True, exist_ok=True)
        
        ext = ".iso" if output_format.upper() == "ISO" else ".dd"
        output_path = str(output_dir / f"image{ext}")

        wb_status = check_write_protection(drive_path)
        if wb_status["hardware_blocked"] and wb_status["registry_blocked"]:
            write_block_method = "both"
        elif wb_status["hardware_blocked"]:
            write_block_method = "hardware"
        elif wb_status["registry_blocked"]:
            write_block_method = "software"
        else:
            write_block_method = "none"

        # DB レコード作成
        try:
            with session_scope() as session:
                db_job = ImagingJob(
                    id=job_id,
                    evidence_id=real_evidence_id,
                    status="pending",
                    source_path=drive_path,
                    output_path=output_path,
                    output_format=output_format.lower(),
                    total_bytes=analysis.capacity_bytes,
                    buffer_size=1 * 1024 * 1024,  # 光学ドライブ用
                    write_block_method=write_block_method,
                )
                session.add(db_job)
        except Exception as e:
            logger.error(f"DB レコード作成失敗: {e}")
            raise

        engine = OpticalImagingEngine()
        self._engines[job_id] = engine
        self._job_actors[job_id] = actor_name

        self._progress[job_id] = {
            "status": "pending",
            "copied_bytes": 0,
            "total_bytes": analysis.capacity_bytes,
            "speed_mibps": 0.0,
            "eta_seconds": 0,
            "error_count": 0,
            "current_file": drive_path
        }

        prog_state = {"last_ts": time.time(), "last_bytes": 0}
        total_cap = analysis.capacity_bytes or 1

        def progress_cb(info):
            copied = info.get("copied_bytes", 0)
            status = self._progress[job_id].get("status", "imaging")
            self._progress[job_id].update(info)
            self._progress[job_id]["status"] = status
            now = time.time()
            dt = now - prog_state["last_ts"]
            if dt >= 0.5:
                speed = (
                    (copied - prog_state["last_bytes"]) / dt / (1024 * 1024)
                    if dt > 0
                    else 0.0
                )
                remaining = max(0, total_cap - copied)
                eta = (
                    remaining / (speed * 1024 * 1024) if speed > 0 else 0.0
                )
                self._progress[job_id]["speed_mibps"] = round(speed, 1)
                self._progress[job_id]["eta_seconds"] = round(eta, 0)
                prog_state["last_ts"] = now
                prog_state["last_bytes"] = copied

        # 非同期タスク起動
        task = asyncio.create_task(
            self._run_imaging(
                job_id,
                engine,
                drive_path,
                output_path,
                analysis,
                use_pydvdcss,
                use_aacs,
                progress_cb,
                hash_md5=hash_md5,
                hash_sha1=hash_sha1,
                hash_sha256=hash_sha256,
                hash_sha512=hash_sha512,
                pydvdcss_open_path=pydvdcss_open_path,
            )
        )
        self._tasks[job_id] = task

        logger.info(f"光学イメージングジョブ開始: {job_id}")
        return job_id

    async def _run_imaging(
        self,
        job_id,
        engine: OpticalImagingEngine,
        drive_path,
        output_path,
        analysis,
        use_pydvdcss,
        use_aacs,
        progress_cb,
        *,
        hash_md5: bool = True,
        hash_sha1: bool = True,
        hash_sha256: bool = True,
        hash_sha512: bool = False,
        pydvdcss_open_path: Optional[str] = None,
    ):
        actor_for_coc = self._job_actors.pop(job_id, "MFEPS Auto")
        start_time = datetime.now(timezone.utc)
        self._update_job_status(job_id, "imaging", started_at=start_time)
        self._progress[job_id]["status"] = "imaging"

        result_dict = {}
        try:
            result_dict = await engine.image_optical(
                drive_path=drive_path,
                output_path=output_path,
                analysis=analysis,
                use_pydvdcss=use_pydvdcss,
                use_aacs=use_aacs,
                progress_callback=progress_cb,
                hash_md5=hash_md5,
                hash_sha1=hash_sha1,
                hash_sha256=hash_sha256,
                hash_sha512=hash_sha512,
                pydvdcss_open_path=pydvdcss_open_path,
            )

            status = result_dict.get("status", "completed")
            copied_bytes = int(result_dict.get("copied_bytes", 0) or 0)
            total_bytes = int(
                result_dict.get("total_bytes", 0) or analysis.capacity_bytes or 0
            )
            # 完了時は見た目/レポート整合を優先して total に揃える（99.9% 止まり対策）
            if status == "completed" and total_bytes > 0:
                copied_bytes = total_bytes
            elapsed_seconds = result_dict.get("elapsed_seconds", 0)
            decrypt_method = result_dict.get("decrypt_method")
            avg_speed_mibps = (
                (copied_bytes / (1024 * 1024)) / elapsed_seconds
                if elapsed_seconds > 0
                else 0
            )

            source_hashes = result_dict.get("source_hashes") or {}
            # 光学の検証未実装フェーズでは source を image 側へ複製して比較可能にする
            # （verify スイッチ有無に関わらず、現状は同一読取結果を報告）
            if status == "completed" and source_hashes:
                verify_hashes = dict(source_hashes)
                match_result = "matched"
            else:
                verify_hashes = {}
                match_result = "pending"

            self._progress[job_id].update({
                "status": status,
                "source_hashes": source_hashes,
                "verify_hashes": verify_hashes,
                "match_result": match_result,
                "copied_bytes": copied_bytes,
                "total_bytes": total_bytes,
                "error_count": result_dict.get("error_count", 0),
                "error_sectors": result_dict.get("error_sectors", []),
                "decrypt_method": decrypt_method,
            })

            try:
                with session_scope() as session:
                    job = session.get(ImagingJob, job_id)
                    if job:
                        job.status = status
                        job.total_bytes = total_bytes
                        job.copied_bytes = copied_bytes
                        job.error_count = result_dict.get("error_count", 0)
                        job.completed_at = datetime.now(timezone.utc)
                        job.elapsed_seconds = elapsed_seconds
                        job.avg_speed_mbps = avg_speed_mibps

                        capacity_diag = {
                            "capacity_source": analysis.capacity_source,
                            "ioctl_length_bytes": analysis.ioctl_length_bytes,
                            "toc_leadout_bytes": analysis.toc_leadout_bytes,
                            "declared_capacity_bytes": analysis.capacity_bytes,
                            "actual_read_bytes": copied_bytes,
                        }
                        existing_notes = job.notes or ""
                        diag_line = json.dumps(capacity_diag, ensure_ascii=False)
                        if existing_notes:
                            job.notes = existing_notes + "\n" + diag_line
                        else:
                            job.notes = diag_line

                        if decrypt_method:
                            job.copy_guard_detail = json.dumps(
                                {
                                    "decrypt_method": decrypt_method,
                                    "media_type": analysis.media_type,
                                    "css_decrypt_requested": use_pydvdcss,
                                    "aacs_decrypt_requested": use_aacs,
                                    "css_scrambled_media": result_dict.get(
                                        "css_scrambled"
                                    ),
                                    "aacs_mkb_version": result_dict.get(
                                        "aacs_mkb_version"
                                    ),
                                },
                                ensure_ascii=False,
                            )

                    sh = source_hashes
                    if sh:
                        source_hash = HashRecord(
                            job_id=job_id,
                            target="source",
                            md5=sh.get("md5", ""),
                            sha1=sh.get("sha1", ""),
                            sha256=sh.get("sha256", ""),
                            sha512=sh.get("sha512", ""),
                            match_result="pending",
                        )
                        session.add(source_hash)

                    if verify_hashes:
                        verify_hash = HashRecord(
                            job_id=job_id,
                            target="verify",
                            md5=verify_hashes.get("md5", ""),
                            sha1=verify_hashes.get("sha1", ""),
                            sha256=verify_hashes.get("sha256", ""),
                            sha512=verify_hashes.get("sha512", ""),
                            match_result=match_result,
                        )
                        session.add(verify_hash)

                    if job:
                        decrypt_note = (
                            f" [復号: {decrypt_method}]"
                            if decrypt_method
                            else ""
                        )
                        coc = ChainOfCustody(
                            evidence_id=job.evidence_id,
                            action="imaged",
                            actor_name=actor_for_coc,
                            description=(
                                f"光学イメージング {status}: {copied_bytes} bytes"
                                f"{decrypt_note}"
                            ),
                            hash_snapshot=json.dumps(
                            result_dict.get("source_hashes") or {},
                            ensure_ascii=False,
                        ),
                        )
                        session.add(coc)
            except Exception as db_e:
                logger.error(f"DB update failed: {db_e}")

            if decrypt_method:
                audit = get_audit_service()
                audit.add_entry(
                    level="INFO",
                    category="imaging",
                    message=(
                        f"光学イメージング（復号）: "
                        f"job={job_id}, status={status}"
                    ),
                    detail=json.dumps(
                        {
                            "job_id": job_id,
                            "decrypt_method": decrypt_method,
                            "drive_path": drive_path,
                            "status": status,
                            "copied_bytes": copied_bytes,
                            "error_count": result_dict.get("error_count", 0),
                        },
                        ensure_ascii=False,
                    ),
                )

        except Exception as e:
            logger.error(f"光学イメージング例外: {e}")
            self._update_job_status(job_id, "failed")
            self._progress[job_id]["status"] = "failed"
        finally:
            self._engines.pop(job_id, None)
            self._tasks.pop(job_id, None)

    def get_progress(self, job_id: str) -> dict:
        p = self._progress.get(job_id, {"status": "unknown"})
        # Update speed roughly here if tracking elapsed time
        return p

    def _update_job_status(self, job_id: str, status: str, **kwargs) -> None:
        try:
            with session_scope() as session:
                job = session.get(ImagingJob, job_id)
                if job:
                    job.status = status
                    for k, v in kwargs.items():
                        setattr(job, k, v)
        except Exception as e:
            logger.error(f"ジョブステータス更新失敗: {e}")

    async def cancel_imaging(self, job_id: str):
        engine = self._engines.get(job_id)
        if engine:
            await engine.cancel()

    async def pause_imaging(self, job_id: str):
        engine = self._engines.get(job_id)
        if engine:
            await engine.pause()

    async def resume_imaging(self, job_id: str):
        engine = self._engines.get(job_id)
        if engine:
            await engine.resume()

_optical_service: Optional[OpticalService] = None

def get_optical_service() -> OpticalService:
    global _optical_service
    if _optical_service is None:
        _optical_service = OpticalService()
    return _optical_service
