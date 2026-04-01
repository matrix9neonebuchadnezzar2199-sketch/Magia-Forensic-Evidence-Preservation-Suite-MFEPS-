"""
ダッシュボード用 DB 集計
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from src.models.database import session_scope
from src.models.schema import Case, EvidenceItem, ImagingJob


def get_dashboard_counts() -> dict[str, int]:
    """総案件数・総証拠品数・総イメージジョブ数・エラーセクタ合計を返す。"""
    with session_scope() as session:
        n_cases = session.query(func.count(Case.id)).scalar() or 0
        n_evidence = session.query(func.count(EvidenceItem.id)).scalar() or 0
        n_jobs = session.query(func.count(ImagingJob.id)).scalar() or 0
        err_sum = session.query(func.coalesce(func.sum(ImagingJob.error_count), 0)).scalar()
        err_sum = int(err_sum or 0)
    return {
        "cases": int(n_cases),
        "evidence": int(n_evidence),
        "images": int(n_jobs),
        "errors": err_sum,
    }


def get_recent_jobs(limit: int = 15) -> list[dict[str, Any]]:
    """最近のイメージングジョブ（日付降順）。"""
    with session_scope() as session:
        q = (
            session.query(ImagingJob)
            .options(
                joinedload(ImagingJob.evidence).joinedload(EvidenceItem.case)
            )
            .order_by(
                func.coalesce(
                    ImagingJob.completed_at, ImagingJob.started_at
                ).desc()
            )
            .limit(limit)
        )
        rows = q.all()

    out: list[dict[str, Any]] = []
    for job in rows:
        ev = job.evidence
        case_no = ""
        ev_no = ""
        media = ""
        if ev:
            ev_no = ev.evidence_number or ""
            media = ev.media_type or ""
            if ev.case:
                case_no = ev.case.case_number or ""

        completed = job.completed_at or job.started_at
        date_s = completed.strftime("%Y-%m-%d %H:%M") if completed else "—"

        dur_s = ""
        if job.elapsed_seconds is not None and job.elapsed_seconds > 0:
            sec = int(job.elapsed_seconds)
            m, s = divmod(sec, 60)
            h, m = divmod(m, 60)
            dur_s = f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"

        out.append(
            {
                "id": job.id,
                "date": date_s,
                "case": case_no,
                "evidence": ev_no,
                "media": media or "—",
                "status": job.status or "—",
                "duration": dur_s or "—",
            }
        )
    return out
