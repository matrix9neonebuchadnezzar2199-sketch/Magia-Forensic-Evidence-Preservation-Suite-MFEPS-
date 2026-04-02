"""
MFEPS v2.3.0 — 統計集計サービス
ダッシュボードのグラフ描画用データを DB から集計する。
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func

from src.models.database import session_scope
from src.models.schema import ImagingJob

logger = logging.getLogger("mfeps.stats_service")

_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


def get_daily_job_counts(days: int = 30) -> dict[str, list]:
    """
    直近 N 日間の日別ジョブ数（完了/失敗/キャンセル）。
    戻り値: {"dates": [...], "completed": [...], "failed": [...], "cancelled": [...]}
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    day_col = func.date(ImagingJob.completed_at)
    with session_scope() as session:
        rows = (
            session.query(day_col, ImagingJob.status, func.count(ImagingJob.id))
            .filter(ImagingJob.completed_at.isnot(None))
            .filter(ImagingJob.completed_at >= cutoff)
            .group_by(day_col, ImagingJob.status)
            .all()
        )

    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"completed": 0, "failed": 0, "cancelled": 0}
    )
    for d, status, cnt in rows:
        ds = str(d) if d else "unknown"
        st = status or ""
        if st in _TERMINAL_STATUSES:
            buckets[ds][st] = int(cnt)

    dates = sorted(buckets.keys())
    return {
        "dates": dates,
        "completed": [buckets[d]["completed"] for d in dates],
        "failed": [buckets[d]["failed"] for d in dates],
        "cancelled": [buckets[d]["cancelled"] for d in dates],
    }


def get_throughput_history(limit: int = 50) -> dict[str, list]:
    """
    直近の完了ジョブのスループット (MiB/s) 推移。
    戻り値: {"labels": [...], "speeds": [...]}
    """
    with session_scope() as session:
        jobs = (
            session.query(ImagingJob)
            .filter(ImagingJob.status == "completed")
            .filter(ImagingJob.avg_speed_mbps > 0)
            .order_by(ImagingJob.completed_at.desc())
            .limit(limit)
            .all()
        )

    jobs = list(reversed(jobs))
    labels = []
    speeds = []
    for j in jobs:
        dt = j.completed_at or j.started_at
        label = dt.strftime("%m/%d %H:%M") if dt else j.id[:8]
        labels.append(label)
        speeds.append(round(float(j.avg_speed_mbps or 0), 1))
    return {"labels": labels, "speeds": speeds}


def get_format_distribution() -> dict[str, int]:
    """出力形式別のジョブ数。"""
    with session_scope() as session:
        rows = (
            session.query(ImagingJob.output_format, func.count(ImagingJob.id))
            .group_by(ImagingJob.output_format)
            .all()
        )
    return {(fmt or "raw"): int(cnt) for fmt, cnt in rows}


def get_error_rate() -> dict[str, Any]:
    """全ジョブの成功率・エラー率。"""
    with session_scope() as session:
        total = session.query(func.count(ImagingJob.id)).scalar() or 0
        completed = (
            session.query(func.count(ImagingJob.id))
            .filter(ImagingJob.status == "completed")
            .scalar()
            or 0
        )
        with_errors = (
            session.query(func.count(ImagingJob.id))
            .filter(ImagingJob.error_count > 0)
            .scalar()
            or 0
        )
    total = int(total)
    completed = int(completed)
    return {
        "total": total,
        "completed": completed,
        "success_rate": round(completed / total * 100, 1) if total > 0 else 0,
        "with_errors": int(with_errors),
    }
