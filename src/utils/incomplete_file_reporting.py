"""
不完全出力ファイルの DB notes 追記と監査ログ（削除は行わない）。
"""
from __future__ import annotations

import json
from typing import Any

from src.services.audit_service import get_audit_service

_NOTICE = (
    "不完全なファイルが出力先に残っています。手動で確認・削除してください。"
)


def append_incomplete_files_report(
    job_id: str,
    reason: str,
    records: list[dict[str, Any]],
    current_notes: str | None,
) -> str:
    """
    ImagingJob.notes に JSON 1行を追記し、監査ログに WARN を残す。
    records が空のときは current_notes をそのまま返す。
    """
    if not records:
        return current_notes or ""

    payload = {
        "type": "incomplete_files",
        "reason": reason,
        "files": records,
        "notice": _NOTICE,
    }
    line = json.dumps(payload, ensure_ascii=False)

    audit = get_audit_service()
    audit.add_entry(
        level="WARN",
        category="imaging",
        message=(
            f"不完全ファイル検出: job={job_id}, reason={reason}, "
            f"count={len(records)}"
        ),
        detail=json.dumps(
            {
                "job_id": job_id,
                "reason": reason,
                "incomplete_files": records,
            },
            ensure_ascii=False,
        ),
    )

    prev = (current_notes or "").strip()
    return (prev + "\n" + line) if prev else line


def incomplete_reason_from_job_status(status: str) -> str:
    if status == "cancelled":
        return "cancelled"
    return "failed"
