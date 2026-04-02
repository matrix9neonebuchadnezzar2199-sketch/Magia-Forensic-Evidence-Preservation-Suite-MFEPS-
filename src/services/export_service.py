"""
MFEPS v2.3.0 — イメージエクスポートサービス
完了ジョブの成果物を zip パッケージにまとめる。
"""
import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path

from src.models.database import session_scope
from src.models.schema import ImagingJob, HashRecord, ChainOfCustody
from src.services.report_service import ReportService
from src.utils.config import get_config

logger = logging.getLogger("mfeps.export_service")


class ExportService:
    """ジョブ成果物を zip にパッケージする"""

    def export_job(
        self,
        job_id: str,
        include_image: bool = True,
        include_report: bool = True,
        include_hash_log: bool = True,
        include_error_map: bool = True,
        include_coc: bool = True,
    ) -> str:
        """
        指定ジョブの成果物を zip にまとめ、パスを返す。

        Returns:
            生成された zip ファイルの絶対パス
        Raises:
            ValueError: ジョブが見つからない
        """
        with session_scope() as session:
            job = session.get(ImagingJob, job_id)
            if not job:
                raise ValueError(f"ジョブが見つかりません: {job_id}")

            job_data = {
                "id": job.id,
                "status": job.status,
                "output_path": job.output_path or "",
                "output_format": job.output_format or "raw",
                "total_bytes": job.total_bytes,
                "copied_bytes": job.copied_bytes,
                "error_count": job.error_count,
                "error_map_path": job.error_map_path or "",
                "evidence_id": job.evidence_id,
                "elapsed_seconds": job.elapsed_seconds,
                "avg_speed_mbps": job.avg_speed_mbps,
            }

            hashes = []
            for hr in session.query(HashRecord).filter_by(job_id=job_id).all():
                hashes.append(
                    {
                        "target": hr.target,
                        "md5": hr.md5,
                        "sha1": hr.sha1,
                        "sha256": hr.sha256,
                        "sha512": getattr(hr, "sha512", "") or "",
                        "match_result": hr.match_result,
                    }
                )

            coc_entries = []
            if include_coc and job.evidence_id:
                for c in (
                    session.query(ChainOfCustody)
                    .filter_by(evidence_id=job.evidence_id)
                    .order_by(ChainOfCustody.timestamp.asc())
                    .all()
                ):
                    coc_entries.append(
                        {
                            "action": c.action,
                            "actor_name": c.actor_name,
                            "description": c.description,
                            "timestamp": str(c.timestamp),
                        }
                    )

        config = get_config()
        export_dir = config.output_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"MFEPS_export_{job_id[:8]}_{ts}.zip"
        zip_path = export_dir / zip_name

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if include_image and job_data["output_path"]:
                img_path = Path(job_data["output_path"])
                if img_path.is_file():
                    zf.write(img_path, f"image/{img_path.name}")
                if job_data["output_format"] == "e01":
                    for seg in sorted(img_path.parent.glob("*.E*")):
                        if seg.suffix.upper().startswith(".E") and seg.is_file():
                            zf.write(seg, f"image/{seg.name}")

            if include_hash_log and hashes:
                zf.writestr(
                    "hash_records.json",
                    json.dumps(hashes, indent=2, ensure_ascii=False),
                )

            if include_error_map and job_data["error_map_path"]:
                em = Path(job_data["error_map_path"])
                if em.is_file():
                    zf.write(em, f"errors/{em.name}")

            if include_coc and coc_entries:
                zf.writestr(
                    "chain_of_custody.json",
                    json.dumps(coc_entries, indent=2, ensure_ascii=False),
                )

            if include_report:
                try:
                    report_svc = ReportService()
                    html_path = report_svc.generate_html(job_id)
                    if html_path:
                        hp = Path(html_path)
                        if hp.is_file():
                            zf.write(hp, f"report/{hp.name}")
                except Exception as e:
                    logger.warning("レポート生成失敗（エクスポート続行）: %s", e)

            zf.writestr(
                "job_metadata.json",
                json.dumps(job_data, indent=2, ensure_ascii=False, default=str),
            )

        logger.info("エクスポート完了: %s", zip_path)
        return str(zip_path.resolve())
