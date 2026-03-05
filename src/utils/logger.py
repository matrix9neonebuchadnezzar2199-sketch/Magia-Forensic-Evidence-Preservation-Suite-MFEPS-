"""
MFEPS v2.0 — ロギング設定
3つのログファイル + コンソール出力
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_initialized = False

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5


def setup_logging(logs_dir: Path, level: str = "INFO") -> None:
    """ロギングを初期化"""
    global _initialized
    if _initialized:
        return
    _initialized = True

    logs_dir.mkdir(parents=True, exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # コンソールハンドラ
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # app.log — 全般
    app_handler = RotatingFileHandler(
        logs_dir / "app.log", maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
        encoding="utf-8")
    app_handler.setLevel(numeric_level)
    app_handler.setFormatter(formatter)
    root_logger.addHandler(app_handler)

    # imaging.log — イメージング専用
    imaging_logger = logging.getLogger("mfeps.imaging")
    imaging_handler = RotatingFileHandler(
        logs_dir / "imaging.log", maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
        encoding="utf-8")
    imaging_handler.setLevel(numeric_level)
    imaging_handler.setFormatter(formatter)
    imaging_logger.addHandler(imaging_handler)

    # audit.log — 監査ログ専用
    audit_logger = logging.getLogger("mfeps.audit")
    audit_handler = RotatingFileHandler(
        logs_dir / "audit.log", maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
        encoding="utf-8")
    audit_handler.setLevel(logging.INFO)  # 監査ログは常にINFO以上
    audit_handler.setFormatter(formatter)
    audit_logger.addHandler(audit_handler)

    logging.getLogger("mfeps").info("MFEPS ロギング初期化完了")


def get_logger(name: str) -> logging.Logger:
    """名前付きロガーを取得"""
    return logging.getLogger(f"mfeps.{name}")
