"""
MFEPS v2.1.0 — イメージング統合サービス
UIとイメージングエンジンを仲介するオーケストレータ
"""
import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable

from src.core.imaging_engine import ImagingEngine, ImagingJobParams, ImagingResult
from src.core.device_detector import DeviceInfo
from src.core.e01_writer import E01InfoResult
from src.core.write_blocker import check_write_protection
from src.models.database import session_scope
from src.models.enums import OutputFormat
from src.models.schema import ImagingJob, HashRecord, ChainOfCustody
from src.utils.audit_categories import AuditCategories
from src.utils.config import get_config
from src.utils.constants import E01_REMAINING_PATTERN
from src.utils.path_sanitize import sanitize_path_component
from src.utils.output_path_helpers import resolve_safe_output_path
from src.utils.storage_helpers import get_general_storage
from src.utils.incomplete_file_reporting import (
    append_incomplete_files_report,
    incomplete_reason_from_job_status,
)


def _parse_e01_remaining_to_seconds(remaining_str: str) -> float:
    """ewfacquire の 'completion in N minute(s) and N second(s)' を秒数に変換。"""
    if not remaining_str:
        return 0.0
    m = E01_REMAINING_PATTERN.search(remaining_str)
    if not m:
        return 0.0
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    return float(hours * 3600 + minutes * 60 + seconds)


logger = logging.getLogger("mfeps.imaging_service")


def _merge_e01_verify_hashes_from_source(
    job: Optional[ImagingJob],
    result: ImagingResult,
) -> Optional[dict]:
    """
    E01 かつ検証一致時、ewfverify が MD5 を返さないビルドでも
    イメージ側 hash_record にソースと同一の raw ハッシュを記録する。
    """
    if not result.verify_hashes or not _hash_dict_has_values(result.verify_hashes):
        return None
    if not job or (job.output_format or "").lower() != "e01":
        return dict(result.verify_hashes)
    if result.match_result != "matched" or not result.source_hashes:
        return dict(result.verify_hashes)
    merged = dict(result.verify_hashes)
    src = result.source_hashes
    for k in ("md5", "sha256", "sha512"):
        if not (merged.get(k) or "").strip() and (src.get(k) or "").strip():
            merged[k] = src[k]
    return merged


def _hash_dict_has_values(h: Optional[dict]) -> bool:
    """空の {} や全キー空文字のときは False（HashRecord を作らない）"""
    if not h:
        return False
    return any((v or "").strip() for v in h.values())


class ImagingService:
    """イメージングオーケストレータ"""

    def __init__(self):
        self._engines: dict[str, ImagingEngine] = {}
        self._e01_writers: dict[str, object] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._results: dict[str, dict] = {}
        self._job_actors: dict[str, str] = {}
        self._e01_info_cache: dict[str, E01InfoResult] = {}


    async def start_imaging(
        self,
        device: DeviceInfo,
        case_id: str,
        evidence_id: str,
        output_format: str = "raw",
        verify: bool = True,
        progress_callback: Optional[Callable] = None,
        actor_name: str = "MFEPS Auto",
        *,
        hash_md5: bool = True,
        hash_sha1: bool = True,
        hash_sha256: bool = True,
        hash_sha512: bool = False,
        e01_examiner_name: str = "",
        e01_description: str = "",
        e01_notes: str = "",
        e01_compression: str = "",
    ) -> str:
        """
        イメージングを開始。
        Returns: job_id
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
            media_type="usb_hdd",
            device_model=device.model,
            device_serial=device.serial,
            capacity_bytes=device.capacity_bytes
        )

        # 出力先ディレクトリ (ユーザー入力はパスサニタイズ)
        safe_case = sanitize_path_component(case_id)
        safe_ev = sanitize_path_component(evidence_id)
        output_dir = config.output_dir / safe_case / safe_ev
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

        if output_format == OutputFormat.E01.value:
            from src.core.e01_writer import E01Writer

            avail = E01Writer.check_available()
            if not avail["ewfacquire_available"]:
                raise RuntimeError(
                    "E01 出力には ewfacquire.exe が必要です。"
                    "libs/ewfacquire.exe を配置するか、設定画面または .env の EWFACQUIRE_PATH を指定してください。"
                )

        _stored = get_general_storage()

        if output_format == OutputFormat.E01.value:
            out_path = resolve_safe_output_path(output_dir, "image", ".E01")
        else:
            out_path = resolve_safe_output_path(output_dir, "image", ".dd")
        comp_str = ""
        seg_for_db = config.e01_segment_size_bytes
        ewf_for_db = config.e01_ewf_format
        if output_format == OutputFormat.E01.value:
            default_comp = (
                f"{config.e01_compression_method}:{config.e01_compression_level}"
            )
            comp_str = e01_compression or _stored.get("e01_compression", default_comp)
            seg_str = _stored.get(
                "e01_segment_size", str(config.e01_segment_size_bytes)
            )
            try:
                seg_for_db = int(seg_str)
            except (ValueError, TypeError):
                seg_for_db = config.e01_segment_size_bytes
            ewf_for_db = _stored.get("e01_ewf_format", config.e01_ewf_format)

        try:
            with session_scope() as session:
                db_job = ImagingJob(
                    id=job_id,
                    evidence_id=real_evidence_id,
                    status="pending",
                    source_path=device.device_path,
                    output_path=str(out_path),
                    output_format=output_format,
                    total_bytes=device.capacity_bytes,
                    buffer_size=config.mfeps_buffer_size,
                    write_block_method=write_block_method,
                    e01_compression=(
                        comp_str if output_format == OutputFormat.E01.value else ""
                    ),
                    e01_segment_size_bytes=(
                        seg_for_db
                        if output_format == OutputFormat.E01.value
                        else 0
                    ),
                    e01_ewf_format=(
                        ewf_for_db
                        if output_format == OutputFormat.E01.value
                        else ""
                    ),
                    e01_examiner_name=(
                        e01_examiner_name
                        if output_format == OutputFormat.E01.value
                        else ""
                    ),
                    e01_notes=(
                        e01_notes if output_format == OutputFormat.E01.value else ""
                    ),
                )
                session.add(db_job)
        except Exception as e:
            logger.error(f"DB レコード作成失敗: {e}")
            raise

        self._job_actors[job_id] = actor_name

        job_params = ImagingJobParams(
            job_id=job_id,
            evidence_id=real_evidence_id,
            case_id=real_case_id,
            source_path=device.device_path,
            output_dir=str(output_dir),
            output_format=output_format,
            buffer_size=config.mfeps_buffer_size,
            verify_after_copy=verify,
            hash_md5=hash_md5,
            hash_sha1=hash_sha1,
            hash_sha256=hash_sha256,
            hash_sha512=hash_sha512,
            case_number_str=case_id,
            evidence_number_str=evidence_id,
        )

        if output_format == OutputFormat.E01.value:
            task = asyncio.create_task(
                self._run_e01_imaging(
                    job_id,
                    job_params,
                    device,
                    e01_examiner_name=e01_examiner_name,
                    e01_description=e01_description,
                    e01_notes=e01_notes,
                    e01_compression=comp_str,
                )
            )
        else:
            engine = ImagingEngine(buffer_size=config.mfeps_buffer_size)
            if progress_callback:
                engine.set_progress_callback(progress_callback)
            self._engines[job_id] = engine
            task = asyncio.create_task(self._run_imaging(job_id, engine, job_params))

        self._tasks[job_id] = task

        logger.info("イメージングジョブ開始: %s (format=%s)", job_id, output_format)
        return job_id

    async def _run_e01_imaging(
        self,
        job_id: str,
        params: ImagingJobParams,
        device: DeviceInfo,
        *,
        e01_examiner_name: str = "",
        e01_description: str = "",
        e01_notes: str = "",
        e01_compression: str = "",
    ) -> None:
        """E01 イメージング — ewfacquire subprocess"""
        from src.core.e01_writer import E01Params, E01Writer
        from src.services.audit_service import get_audit_service

        audit = get_audit_service()
        config = get_config()

        self._update_job_status(
            job_id, "imaging", started_at=datetime.now(timezone.utc)
        )

        writer = E01Writer()
        self._e01_writers[job_id] = writer

        def on_e01_progress(p: dict) -> None:
            self._results[job_id] = {
                **self._results.get(job_id, {}),
                "status": "imaging",
                "copied_bytes": 0,
                "total_bytes": device.capacity_bytes,
                "speed_mibps": 0.0,
                "e01_percent": p.get("percent", 0),
            }

        writer.set_progress_callback(on_e01_progress)

        _stored = get_general_storage()

        default_comp = (
            f"{config.e01_compression_method}:{config.e01_compression_level}"
        )
        if e01_compression:
            compression_str = e01_compression
        else:
            compression_str = _stored.get("e01_compression", default_comp)
        comp_parts = compression_str.split(":", 1)
        cm = comp_parts[0].strip() if comp_parts else "deflate"
        cl = comp_parts[1].strip() if len(comp_parts) > 1 else "fast"

        seg_str = _stored.get(
            "e01_segment_size", str(config.e01_segment_size_bytes)
        )
        try:
            seg_bytes = int(seg_str)
        except (ValueError, TypeError):
            seg_bytes = config.e01_segment_size_bytes

        ewf_fmt = _stored.get("e01_ewf_format", config.e01_ewf_format)

        output_stem = "image"
        with session_scope() as session:
            dbj = session.get(ImagingJob, job_id)
            if dbj and dbj.output_path:
                output_stem = Path(dbj.output_path).stem

        e01_params = E01Params(
            source_path=params.source_path,
            output_dir=params.output_dir,
            output_basename=output_stem,
            case_number=params.case_number_str,
            evidence_number=params.evidence_number_str,
            examiner_name=e01_examiner_name,
            description=e01_description,
            notes=e01_notes,
            compression_method=cm,
            compression_level=cl,
            segment_size_bytes=seg_bytes,
            ewf_format=ewf_fmt,
            media_type=(
                "removable"
                if device.interface_type.upper() == "USB"
                or "USB" in (device.media_type or "").upper()
                else "fixed"
            ),
            calculate_sha256=True,
        )

        audit.add_entry(
            level="INFO",
            category=AuditCategories.E01_START,
            message=f"E01 取得開始: {params.source_path}",
            detail=json.dumps(
                {
                    "job_id": job_id,
                    "source": params.source_path,
                    "format": "e01",
                    "ewf_format": e01_params.ewf_format,
                    "compression": f"{e01_params.compression_method}:"
                    f"{e01_params.compression_level}",
                },
                ensure_ascii=False,
            ),
        )

        try:
            e01_result = await writer.acquire(e01_params)

            audit.add_entry(
                level="INFO",
                category=AuditCategories.E01_COMPLETE,
                message=(
                    f"ewfacquire 実行完了: code={e01_result.ewfacquire_return_code}"
                ),
                detail=json.dumps(
                    {
                        "job_id": job_id,
                        "command_line": e01_result.command_line,
                        "ewfacquire_version": e01_result.ewfacquire_version,
                        "return_code": e01_result.ewfacquire_return_code,
                    },
                    ensure_ascii=False,
                ),
            )

            try:
                with session_scope() as session:
                    job = session.get(ImagingJob, job_id)
                    if job:
                        job.e01_command_line = e01_result.command_line
                        job.e01_ewfacquire_version = e01_result.ewfacquire_version
                        job.e01_segment_count = e01_result.segment_count
                        job.e01_log_path = e01_result.log_file_path
                        if e01_result.output_files:
                            job.output_path = e01_result.output_files[0]
            except Exception as e:
                logger.error("E01 DB 更新失敗: %s", e)

            verify_hashes = None
            match_result = "pending"

            if e01_result.success and params.verify_after_copy:
                verify = await writer.verify(e01_result.output_files[0])

                if verify.skipped:
                    match_result = "pending"
                    audit.add_entry(
                        level="WARN",
                        category=AuditCategories.HASH_VERIFY,
                        message=f"E01 検証スキップ: {verify.skip_reason}",
                        detail=json.dumps({"job_id": job_id}, ensure_ascii=False),
                    )
                elif verify.verified:
                    match_result = "matched"
                    verify_hashes = {
                        "md5": verify.computed_hashes.get("MD5", ""),
                        "sha256": verify.computed_hashes.get("SHA256", ""),
                    }
                    audit.add_entry(
                        level="INFO",
                        category=AuditCategories.HASH_VERIFY,
                        message="E01 検証成功: 全ハッシュ一致",
                        detail=json.dumps(
                            {
                                "job_id": job_id,
                                "stored": verify.stored_hashes,
                                "computed": verify.computed_hashes,
                            },
                            ensure_ascii=False,
                        ),
                    )
                else:
                    match_result = "mismatched"
                    verify_hashes = {
                        "md5": verify.computed_hashes.get("MD5", ""),
                        "sha256": verify.computed_hashes.get("SHA256", ""),
                    }
                    audit.add_entry(
                        level="ERROR",
                        category=AuditCategories.HASH_MISMATCH,
                        message="E01 検証失敗: ハッシュ不一致",
                        detail=json.dumps(
                            {
                                "job_id": job_id,
                                "stored": verify.stored_hashes,
                                "computed": verify.computed_hashes,
                            },
                            ensure_ascii=False,
                        ),
                    )

            if e01_result.success and e01_result.output_files:
                e01_first = e01_result.output_files[0]
                if len(e01_first) > 240:
                    logger.warning(
                        "ewfinfo をスキップ: パスが長すぎます (%s)",
                        e01_first[:120],
                    )
                else:
                    try:
                        info_result = await writer.info(e01_first)
                        if info_result.success:
                            self._e01_info_cache[job_id] = info_result
                            payload = json.dumps(
                                {
                                    "type": "ewfinfo",
                                    "sections": info_result.sections,
                                    "raw_excerpt": info_result.raw_output[:8000],
                                },
                                ensure_ascii=False,
                            )
                            with session_scope() as session:
                                j = session.get(ImagingJob, job_id)
                                if j:
                                    prev = (j.notes or "").strip()
                                    j.notes = (prev + "\n" + payload) if prev else payload
                    except Exception as ex:
                        logger.warning("ewfinfo 取得失敗: %s", ex)

            if e01_result.error_code == "E3006":
                status = "cancelled"
            elif e01_result.success:
                status = "completed"
            else:
                status = "failed"

            avg_mib = 0.0
            if (
                e01_result.elapsed_seconds > 0
                and e01_result.acquired_bytes > 0
            ):
                avg_mib = e01_result.acquired_bytes / (
                    e01_result.elapsed_seconds * 1024 * 1024
                )

            # E01 / libewf はストリーム上 MD5・SHA-256 のみ。ImagingResult.sha1 は RAW 専用で空のまま。
            imaging_result = ImagingResult(
                job_id=job_id,
                status=status,
                source_hashes={
                    "md5": e01_result.md5,
                    "sha256": e01_result.sha256,
                },
                verify_hashes=verify_hashes,
                match_result=match_result,
                total_bytes=e01_result.total_bytes,
                copied_bytes=e01_result.acquired_bytes,
                elapsed_seconds=e01_result.elapsed_seconds,
                avg_speed_mibps=avg_mib,
                output_path=(
                    e01_result.output_files[0] if e01_result.output_files else ""
                ),
                error_code=e01_result.error_code or None,
                error_message=e01_result.error_message or None,
                incomplete_files=list(e01_result.incomplete_files),
                incomplete_total_bytes=e01_result.incomplete_total_bytes,
                incomplete_file_records=list(e01_result.incomplete_file_records),
            )

            await self.on_imaging_complete(imaging_result)

        except asyncio.CancelledError:
            self._job_actors.pop(job_id, None)
            self._update_job_status(job_id, "cancelled")
            logger.info("E01 イメージングタスクがキャンセル: %s", job_id)
            raise
        except (OSError, IOError) as e:
            logger.error("E01 イメージング I/O エラー: %s", e, exc_info=True)
            self._job_actors.pop(job_id, None)
            self._update_job_status(job_id, "failed")
            self._results[job_id] = {
                "status": "failed",
                "error_message": str(e),
            }
            audit.add_entry(
                level="ERROR",
                category=AuditCategories.E01_FAIL,
                message=f"E01 取得 I/O 失敗: {e}",
                detail=json.dumps({"job_id": job_id}, ensure_ascii=False),
            )
        except Exception as e:
            logger.error("E01 イメージングタスクエラー: %s", e, exc_info=True)
            self._job_actors.pop(job_id, None)
            self._update_job_status(job_id, "failed")
            self._results[job_id] = {
                "status": "failed",
                "error_message": str(e),
            }
            audit.add_entry(
                level="ERROR",
                category=AuditCategories.E01_FAIL,
                message=f"E01 取得失敗: {e}",
                detail=json.dumps({"job_id": job_id}, ensure_ascii=False),
            )
        finally:
            self._e01_writers.pop(job_id, None)
            self._tasks.pop(job_id, None)

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
        except asyncio.CancelledError:
            self._job_actors.pop(job_id, None)
            self._update_job_status(job_id, "cancelled")
            logger.info("イメージングタスクがキャンセルされました: %s", job_id)
            raise
        except (OSError, IOError) as e:
            logger.error("イメージング I/O エラー: %s", e, exc_info=True)
            self._job_actors.pop(job_id, None)
            self._update_job_status(job_id, "failed")
            self._results[job_id] = {
                "status": "failed",
                "error_message": str(e),
            }
        except Exception as e:
            logger.error("イメージングタスクエラー: %s", e, exc_info=True)
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
        job = None
        verify_for_cache = result.verify_hashes
        try:
            with session_scope() as session:
                job = session.get(ImagingJob, result.job_id)
                if job:
                    job.status = result.status
                    # total_bytes は UI/報告書で参照されるため、DB作成時の WMI 値ではなく
                    # エンジンが取得した Win32 IOCTL 値で統一する
                    job.total_bytes = result.total_bytes
                    job.copied_bytes = result.copied_bytes
                    job.error_count = result.error_count
                    job.completed_at = datetime.now(timezone.utc)
                    job.elapsed_seconds = result.elapsed_seconds
                    job.avg_speed_mbps = result.avg_speed_mibps
                    if result.error_code or result.error_message:
                        code = (result.error_code or "").strip()
                        msg = (result.error_message or "").strip()
                        if code and msg:
                            job.notes = f"[{code}] {msg}"
                        elif code:
                            job.notes = f"[{code}]"
                        elif msg:
                            job.notes = msg
                    if result.output_path:
                        job.output_path = result.output_path

                    if result.incomplete_file_records:
                        job.notes = append_incomplete_files_report(
                            result.job_id,
                            incomplete_reason_from_job_status(result.status),
                            result.incomplete_file_records,
                            job.notes,
                        )

                if _hash_dict_has_values(result.source_hashes):
                    source_hash = HashRecord(
                        job_id=result.job_id,
                        target="source",
                        md5=result.source_hashes.get("md5", ""),
                        sha1=result.source_hashes.get("sha1", ""),
                        sha256=result.source_hashes.get("sha256", ""),
                        sha512=result.source_hashes.get("sha512", ""),
                        match_result="pending",
                    )
                    session.add(source_hash)

                verify_for_db = _merge_e01_verify_hashes_from_source(
                    job, result
                )
                if verify_for_db is not None:
                    verify_for_cache = verify_for_db
                if verify_for_db and _hash_dict_has_values(verify_for_db):
                    verify_hash = HashRecord(
                        job_id=result.job_id,
                        target="verify",
                        md5=verify_for_db.get("md5", ""),
                        sha1=verify_for_db.get("sha1", ""),
                        sha256=verify_for_db.get("sha256", ""),
                        sha512=verify_for_db.get("sha512", ""),
                        match_result=result.match_result,
                    )
                    session.add(verify_hash)

                if job:
                    coc = ChainOfCustody(
                        evidence_id=job.evidence_id,
                        action="imaged",
                        actor_name=actor_name,
                        description=f"イメージング {result.status}: "
                                    f"{result.copied_bytes} bytes, "
                                    f"{result.elapsed_seconds}s",
                        hash_snapshot=json.dumps(
                            result.source_hashes, ensure_ascii=False
                        ),
                    )
                    session.add(coc)

                logger.info(f"DB更新完了: job_id={result.job_id}")

        except Exception as e:
            logger.error(f"DB更新失敗: {e}")

        self._results[result.job_id] = {
            "status": result.status,
            "source_hashes": result.source_hashes,
            "verify_hashes": verify_for_cache,
            "match_result": result.match_result,
            "total_bytes": result.total_bytes,
            "copied_bytes": result.copied_bytes,
            "error_count": result.error_count,
            "error_sectors": result.error_sectors,
            "elapsed_seconds": result.elapsed_seconds,
            "avg_speed_mibps": result.avg_speed_mibps,
            "output_path": result.output_path,
            "error_message": result.error_message or "",
            "incomplete_files": result.incomplete_file_records,
        }

    def get_e01_info(self, job_id: str) -> Optional[E01InfoResult]:
        """ewfinfo パース結果（メモリキャッシュまたは job.notes の JSON）。"""
        cached = self._e01_info_cache.get(job_id)
        if cached is not None:
            return cached
        try:
            with session_scope() as session:
                job = session.get(ImagingJob, job_id)
                if not job or not (job.notes or "").strip():
                    return None
                for line in reversed((job.notes or "").split("\n")):
                    line = line.strip()
                    if not line.startswith("{"):
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("type") != "ewfinfo" or "sections" not in obj:
                        continue
                    raw_ex = obj.get("raw_excerpt") or ""
                    r = E01InfoResult(
                        success=True,
                        sections=obj.get("sections") or {},
                        raw_output=raw_ex,
                    )
                    ln0 = raw_ex.splitlines()[0] if raw_ex else ""
                    if ln0.strip().lower().startswith("ewfinfo"):
                        r.ewfinfo_version = ln0.replace("ewfinfo", "", 1).strip()
                    self._e01_info_cache[job_id] = r
                    return r
        except Exception as ex:
            logger.warning("get_e01_info 失敗: %s", ex)
        return None

    def get_progress(self, job_id: str) -> dict:
        """実行中ジョブの進捗を取得"""
        engine = self._engines.get(job_id)
        if engine:
            return engine.get_progress()
        writer = self._e01_writers.get(job_id)
        if writer:
            p = writer.get_progress()
            acquired = int(p.get("acquired_bytes") or 0)
            total = int(p.get("total_bytes") or 0)
            speed_b = int(p.get("speed_bytes") or 0)
            speed_mibps = (
                speed_b / (1024 * 1024) if speed_b > 0 else 0.0
            )
            eta = _parse_e01_remaining_to_seconds(
                p.get("remaining") or ""
            )
            return {
                "status": p.get("status", "imaging"),
                "copied_bytes": acquired,
                "total_bytes": total,
                "speed_mibps": speed_mibps,
                "e01_percent": p.get("percent", 0),
                "eta_seconds": eta,
                "error_count": 0,
                "e01_remaining": p.get("remaining", ""),
                "e01_speed_display": p.get("speed_display", ""),
            }
        if job_id in self._results:
            return self._results[job_id]
        return {"status": "unknown"}

    async def cancel_imaging(self, job_id: str) -> None:
        """イメージングをキャンセル（RAW / E01）"""
        w = self._e01_writers.get(job_id)
        if w:
            await w.cancel()
            self._update_job_status(job_id, "cancelled")
            return
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
        try:
            with session_scope() as session:
                job = session.get(ImagingJob, job_id)
                if job:
                    job.status = status
                    for k, v in kwargs.items():
                        setattr(job, k, v)
        except Exception as e:
            logger.error(f"ジョブステータス更新失敗: {e}")


# シングルトン
_imaging_service: Optional[ImagingService] = None
_imaging_service_lock = threading.Lock()


def get_imaging_service() -> ImagingService:
    global _imaging_service
    if _imaging_service is not None:
        return _imaging_service
    with _imaging_service_lock:
        if _imaging_service is None:
            _imaging_service = ImagingService()
    return _imaging_service
