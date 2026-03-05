"""
MFEPS v2.0 — SQLite データベース接続・初期化
WALモード, 自動テーブル生成
"""
import logging
from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session

from src.models.schema import Base

logger = logging.getLogger("mfeps.database")

_engine = None
_session_factory = None


def init_database(db_path: Path) -> None:
    """データベースを初期化"""
    global _engine, _session_factory

    db_path.parent.mkdir(parents=True, exist_ok=True)

    db_url = f"sqlite:///{db_path}"
    _engine = create_engine(db_url, echo=False, future=True)

    # WAL モード設定 + 外部キー有効化
    @event.listens_for(_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # テーブル自動生成
    Base.metadata.create_all(_engine)

    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)

    logger.info(f"データベース初期化完了: {db_path}")


def get_session() -> Session:
    """新しいセッションを取得"""
    if _session_factory is None:
        raise RuntimeError("データベースが初期化されていません。init_database() を先に呼び出してください。")
    return _session_factory()


def get_engine():
    """エンジンを取得"""
    return _engine


def reset_database(db_path: Path) -> None:
    """データベースを初期化（全データ削除）"""
    global _engine, _session_factory
    if _engine:
        _engine.dispose()
        _engine = None
        _session_factory = None

    if db_path.exists():
        db_path.unlink()
        logger.warning(f"データベース削除: {db_path}")

    init_database(db_path)
    logger.info("データベースを再初期化しました")
