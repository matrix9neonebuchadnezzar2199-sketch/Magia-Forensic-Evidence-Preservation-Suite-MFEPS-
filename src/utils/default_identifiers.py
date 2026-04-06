"""案件番号・証拠品番号の既定値（日時 + 媒体タグ）"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


def default_case_evidence_ids(media_tag: str) -> tuple[str, str]:
    """
    同一形式の案件番号・証拠品番号を生成する。
    形式: YYYYMMDD-HHMM_TAG 例: 20260406-1705_USB
    """
    raw = (media_tag or "MEDIA").strip() or "MEDIA"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in raw)
    safe = safe.strip("_") or "MEDIA"
    now = datetime.now()
    s = f"{now:%Y%m%d-%H%M}_{safe}"
    return (s, s)


def optical_media_tag_for_default(analysis: Optional[Any]) -> str:
    """光学メディア解析結果から既定タグ（USB ページと揃えた短い英字）。"""
    if analysis is None:
        return "DVD"
    mt = (getattr(analysis, "media_type", None) or "").upper()
    if "BD" in mt:
        return "BD"
    if "DVD" in mt:
        return "DVD"
    if "CD" in mt:
        return "CD"
    return "OPTICAL"


def apply_default_case_evidence_inputs(
    case_input: Any,
    ev_input: Any,
    media_tag: str,
) -> None:
    """両方空のときだけ既定値を入れる（ユーザーが消して書き換え可能）。"""
    if (getattr(case_input, "value", None) or "").strip():
        return
    if (getattr(ev_input, "value", None) or "").strip():
        return
    dc, de = default_case_evidence_ids(media_tag)
    case_input.value = dc
    ev_input.value = de
