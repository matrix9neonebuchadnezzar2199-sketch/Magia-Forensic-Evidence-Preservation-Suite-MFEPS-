"""レポート・CoC 等の出力先: reports/<案件名>/"""
from __future__ import annotations

from pathlib import Path

from src.utils.config import get_config
from src.utils.path_sanitize import sanitize_path_component


def case_reports_dir(case_name: str, *, case_number: str = "") -> Path:
    """
    `reports_dir` 直下に案件フォルダを作成して返す。
    案件名が空または N/A のときは案件番号、それも無ければ unnamed。
    """
    cn = (case_name or "").strip()
    num = (case_number or "").strip()
    if cn and cn != "N/A":
        label = cn
    elif num and num != "N/A":
        label = num
    else:
        label = "unnamed"
    safe = sanitize_path_component(label)
    p = get_config().reports_dir / safe
    p.mkdir(parents=True, exist_ok=True)
    return p
