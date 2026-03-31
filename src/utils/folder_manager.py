"""
MFEPS v2.1.0 — フォルダ自動生成
起動時に必要なディレクトリ構造を作成
"""
from pathlib import Path
import logging

logger = logging.getLogger("mfeps.folder_manager")


def ensure_project_structure(base_dir: Path) -> None:
    """必要なフォルダ構造を自動作成"""
    directories = [
        base_dir / "data",
        base_dir / "output",
        base_dir / "logs",
        base_dir / "reports",
        base_dir / "templates",
        base_dir / "backup",
        base_dir / "libs",
    ]

    for d in directories:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            logger.info(f"フォルダ作成: {d}")

    logger.info("プロジェクトフォルダ構造の確認完了")
