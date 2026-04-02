"""
MFEPS v2.1.0 — 出力パスヘルパー
"""
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("mfeps.output_path_helpers")


def resolve_safe_output_path(
    output_dir: Path,
    basename: str,
    extension: str,
) -> Path:
    """
    出力ファイルパスを生成する。同名ファイルが既に存在する場合は
    タイムスタンプ付きの代替名を返し、WARNING ログを記録する。
    """
    candidate = output_dir / f"{basename}{extension}"

    if not candidate.exists():
        return candidate

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    new_name = f"{basename}_{ts}{extension}"
    new_path = output_dir / new_name

    counter = 1
    while new_path.exists():
        new_name = f"{basename}_{ts}_{counter}{extension}"
        new_path = output_dir / new_name
        counter += 1

    logger.warning(
        "出力ファイル %s は既に存在します — %s にリネームしました",
        candidate.name,
        new_path.name,
    )

    return new_path
