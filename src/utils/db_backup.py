"""
MFEPS v2.1.0 — SQLite 自動バックアップ
"""
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.utils.config import get_config

logger = logging.getLogger("mfeps.db_backup")

_MAX_BACKUPS = 5  # 保持するバックアップ世代数


def create_backup(reason: str = "auto") -> Path | None:
    """
    現在の DB ファイルを backup/ にコピー。
    古いバックアップは _MAX_BACKUPS 世代を超えたら削除。

    Args:
        reason: バックアップ理由（ファイル名に付与）

    Returns:
        バックアップファイルパス。失敗時は None。
    """
    config = get_config()
    db_path = config.db_path

    if not db_path.exists():
        logger.warning("DB ファイルが存在しません: %s", db_path)
        return None

    backup_dir = config.backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_name = f"mfeps_{reason}_{ts}.db"
    backup_path = backup_dir / backup_name

    try:
        shutil.copy2(str(db_path), str(backup_path))
        logger.info("DB バックアップ作成: %s", backup_path)

        _rotate_backups(backup_dir)

        return backup_path
    except OSError as e:
        logger.error("DB バックアップ失敗: %s", e)
        return None


def _rotate_backups(backup_dir: Path) -> None:
    """古いバックアップファイルを削除して _MAX_BACKUPS 以内に保つ。"""
    backups = sorted(
        backup_dir.glob("mfeps_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[_MAX_BACKUPS:]:
        try:
            old.unlink()
            logger.info("古いバックアップ削除: %s", old.name)
        except OSError as e:
            logger.warning("バックアップ削除失敗: %s — %s", old.name, e)


def list_backups() -> list[dict]:
    """利用可能なバックアップ一覧を返す。"""
    config = get_config()
    backup_dir = config.backup_dir
    if not backup_dir.exists():
        return []

    result = []
    for p in sorted(backup_dir.glob("mfeps_*.db"), reverse=True):
        result.append({
            "filename": p.name,
            "path": str(p),
            "size_bytes": p.stat().st_size,
            "modified": datetime.fromtimestamp(
                p.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
        })
    return result
