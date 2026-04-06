import asyncio
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.core.hash_engine import verify_image_hash
from src.core.optical_engine import (
    OpticalAnalysisResult,
    OpticalImagingEngine,
    OpticalImagingResult,
)
from src.core.write_blocker import check_write_protection
from src.models.database import session_scope
from src.models.schema import ChainOfCustody, HashRecord, ImagingJob
from src.services.audit_service import get_audit_service
from src.utils.audit_categories import AuditCategories
from src.utils.config import get_config
from src.utils.incomplete_file_detector import detect_incomplete_files
from src.utils.incomplete_file_reporting import (
    append_incomplete_files_report,
    incomplete_reason_from_job_status,
)
from src.utils.long_path import maybe_extend_path
from src.utils.output_path_helpers import resolve_safe_output_path
from src.utils.path_sanitize import sanitize_path_component
from src.utils.rfc3161_client import RFC3161Client
from src.services.coc_service import record_imaging_job_cancelled_coc
from src.ui.session_auth import get_current_actor_name

logger = logging.getLogger("mfeps.optical_service")


def _schedule_optical_progress_publish(job_id: str, payload: dict) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return
    from src.services.progress_broadcaster import get_broadcaster
    loop.create_task(get_broadcaster().publish(job_id, payload))

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
        """
        光学ドライブからイメージ（ISO/RAW）を取得し、DB・進捗を更新する。

        verify が True の場合、完了後に出力ファイルを再読取して source_hashes と照合する。
        """
        config = get_config()
        job_id = str(uuid.uuid4())

        # CaseService は本モジュールと相互 import しうるため遅延 import（循環回避）
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
        output_dir = maybe_extend_path(config.output_dir / safe_case / safe_ev)
        output_dir.mkdir(parents=True, exist_ok=True)

        ext = ".iso" if output_format.upper() == "ISO" else ".dd"
        output_path = str(resolve_safe_output_path(output_dir, "image", ext))

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
            _schedule_optical_progress_publish(job_id, dict(self._progress[job_id]))

        from src.core.job_queue import JobPriority, get_job_queue

        _, task = await get_job_queue().submit(
            job_id,
            lambda: self._run_imaging(
                job_id,
                engine,
                drive_path,
                output_path,
                analysis,
                use_pydvdcss,
                use_aacs,
                progress_cb,
                verify=verify,
                hash_md5=hash_md5,
                hash_sha1=hash_sha1,
                hash_sha256=hash_sha256,
                hash_sha512=hash_sha512,
                pydvdcss_open_path=pydvdcss_open_path,
            ),
            JobPriority.NORMAL,
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
        verify: bool = True,
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

        copy_guard_result = None
        try:
            from src.core.copy_guard_analyzer import CopyGuardAnalyzer

            copy_guard_result = CopyGuardAnalyzer().analyze(
                drive_path,
                analysis,
                pydvdcss_open_path=pydvdcss_open_path,
                timeout=30.0,
            )
        except Exception as ex:
            logger.warning(
                "CopyGuard 分析失敗: %s — 続行します", ex, exc_info=True
            )

        img_result = OpticalImagingResult()
        try:
            img_result = await engine.image_optical(
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
                copy_guard_result=copy_guard_result,
            )

            status = img_result.status
            copied_bytes = int(img_result.copied_bytes or 0)
            total_bytes = int(
                img_result.total_bytes or analysis.capacity_bytes or 0
            )
            # 完了時は見た目/レポート整合を優先して total に揃える（99.9% 止まり対策）
            if status == "completed" and total_bytes > 0:
                copied_bytes = total_bytes
            elapsed_seconds = img_result.elapsed_seconds
            decrypt_method = img_result.decrypt_method
            avg_speed_mibps = (
                (copied_bytes / (1024 * 1024)) / elapsed_seconds
                if elapsed_seconds > 0
                else 0
            )

            source_hashes = dict(img_result.source_hashes)
            verify_hashes: dict = {}
            match_result = "pending"

            if status == "completed" and source_hashes and verify:
                self._progress[job_id]["status"] = "verifying"
                loop = asyncio.get_running_loop()

                def _do_verify() -> dict:
                    return verify_image_hash(
                        output_path,
                        source_hashes,
                        buffer_size=1 * 1024 * 1024,
                        cancel_event=engine._cancel_event,
                        md5=hash_md5,
                        sha1=hash_sha1,
                        sha256=hash_sha256,
                        sha512=hash_sha512,
                    )

                try:
                    vres = await loop.run_in_executor(None, _do_verify)
                    verify_hashes = dict(vres.get("computed") or {})
                    match_result = (
                        "matched" if vres.get("all_match") else "mismatched"
                    )
                    if not vres.get("all_match"):
                        audit = get_audit_service()
                        audit.add_entry(
                            level="ERROR",
                            category=AuditCategories.HASH_MISMATCH,
                            message=(
                                f"光学イメージ検証: ハッシュ不一致 job={job_id}"
                            ),
                            detail=json.dumps(
                                {
                                    "job_id": job_id,
                                    "expected": source_hashes,
                                    "computed": verify_hashes,
                                },
                                ensure_ascii=False,
                            ),
                        )
                except Exception as ver_e:
                    logger.error("光学イメージ検証エラー: %s", ver_e, exc_info=True)
                    verify_hashes = {}
                    match_result = "pending"
                    audit = get_audit_service()
                    audit.add_entry(
                        level="WARN",
                        category=AuditCategories.HASH_VERIFY,
                        message=f"光学イメージ検証失敗: {ver_e}",
                        detail=json.dumps({"job_id": job_id}, ensure_ascii=False),
                    )
            elif status == "completed" and source_hashes and not verify:
                verify_hashes = {}
                match_result = "pending"

            incomplete_records: list[dict] = []
            if status in ("cancelled", "failed"):
                incomplete_records = detect_incomplete_files(
                    str(Path(output_path).parent),
                    [
                        "image*.iso",
                        "image*.dd",
                        "image.iso",
                        "image.dd",
                    ],
                )

            self._progress[job_id].update({
                "status": status,
                "source_hashes": source_hashes,
                "verify_hashes": verify_hashes,
                "match_result": match_result,
                "copied_bytes": copied_bytes,
                "total_bytes": total_bytes,
                "error_count": img_result.error_count,
                "error_sectors": list(img_result.error_sectors),
                "decrypt_method": decrypt_method,
                "incomplete_files": incomplete_records,
            })

            try:
                with session_scope() as session:
                    job = session.get(ImagingJob, job_id)
                    if job:
                        job.status = status
                        job.total_bytes = total_bytes
                        job.copied_bytes = copied_bytes
                        job.error_count = img_result.error_count
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

                        optical_meta = {
                            "media_type": analysis.media_type,
                            "file_system": analysis.file_system,
                            "sector_size": analysis.sector_size,
                            "capacity_bytes": analysis.capacity_bytes,
                            "capacity_source": analysis.capacity_source,
                            "track_count": len(analysis.tracks)
                            if analysis.tracks
                            else 0,
                        }
                        job.notes = (job.notes or "") + "\n" + json.dumps(
                            optical_meta, ensure_ascii=False
                        )

                        if incomplete_records:
                            job.notes = append_incomplete_files_report(
                                job_id,
                                incomplete_reason_from_job_status(status),
                                incomplete_records,
                                job.notes,
                            )

                        if decrypt_method:
                            job.copy_guard_detail = json.dumps(
                                {
                                    "decrypt_method": decrypt_method,
                                    "media_type": analysis.media_type,
                                    "css_decrypt_requested": use_pydvdcss,
                                    "aacs_decrypt_requested": use_aacs,
                                    "css_scrambled_media": img_result.css_scrambled,
                                    "aacs_mkb_version": img_result.aacs_mkb_version,
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
                        RFC3161Client().apply_to_source_hash_record(source_hash)

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
                                img_result.source_hashes,
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
                    category=AuditCategories.DECRYPT_USED,
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
                            "error_count": img_result.error_count,
                        },
                        ensure_ascii=False,
                    ),
                )

        except asyncio.CancelledError:
            self._update_job_status(job_id, "cancelled")
            self._progress[job_id]["status"] = "cancelled"
            logger.info("光学イメージングがキャンセル: %s", job_id)
            raise
        except (OSError, IOError) as e:
            logger.error("光学イメージング I/O エラー: %s", e, exc_info=True)
            self._update_job_status(job_id, "failed")
            self._progress[job_id]["status"] = "failed"
        except Exception as e:
            logger.error("光学イメージング例外: %s", e, exc_info=True)
            self._update_job_status(job_id, "failed")
            self._progress[job_id]["status"] = "failed"
        finally:
            from src.services.progress_broadcaster import get_broadcaster
            st = self._progress.get(job_id, {}).get("status", "")
            if st in ("completed", "failed", "cancelled"):
                get_broadcaster().clear_job(job_id)
            self._engines.pop(job_id, None)
            self._tasks.pop(job_id, None)

    def get_progress(self, job_id: str) -> dict:
        from src.services.progress_broadcaster import get_broadcaster
        base = dict(self._progress.get(job_id, {"status": "unknown"}))
        latest = get_broadcaster().get_latest(job_id)
        if latest:
            merged = {**base}
            for k, v in latest.items():
                if k != "job_id":
                    merged[k] = v
            return merged
        return base

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
            self._update_job_status(job_id, "cancelled")
            record_imaging_job_cancelled_coc(job_id, get_current_actor_name())

    async def pause_imaging(self, job_id: str):
        engine = self._engines.get(job_id)
        if engine:
            await engine.pause()

    async def resume_imaging(self, job_id: str):
        engine = self._engines.get(job_id)
        if engine:
            await engine.resume()

_optical_service: Optional[OpticalService] = None
_optical_service_lock = threading.Lock()


def get_optical_service() -> OpticalService:
    global _optical_service
    if _optical_service is not None:
        return _optical_service
    with _optical_service_lock:
        if _optical_service is None:
            _optical_service = OpticalService()
    return _optical_service
