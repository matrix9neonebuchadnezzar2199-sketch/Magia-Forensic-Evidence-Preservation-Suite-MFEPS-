"""
MFEPS v2.0 — SQLite データベース接続・初期化
WALモード, 自動テーブル生成
"""
import logging
from contextlib import contextmanager
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

    # 既存 DB 向け: imaging_jobs.write_block_method（Phase 3.4）
    with _engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(imaging_jobs)")).fetchall()
        col_names = {r[1] for r in rows}
        if "write_block_method" not in col_names:
            conn.execute(
                text(
                    "ALTER TABLE imaging_jobs ADD COLUMN write_block_method "
                    "VARCHAR(20) DEFAULT 'none'"
                )
            )
            conn.commit()
            logger.info("マイグレーション: imaging_jobs.write_block_method を追加しました")

    # 既存 DB 向け: audit_log.hash_timestamp_iso
    with _engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(audit_log)")).fetchall()
        col_names = {r[1] for r in rows}
        if "hash_timestamp_iso" not in col_names:
            conn.execute(
                text("ALTER TABLE audit_log ADD COLUMN hash_timestamp_iso VARCHAR(64) DEFAULT ''")
            )
            conn.commit()
            logger.info("マイグレーション: audit_log.hash_timestamp_iso を追加しました")

    # hash_records.sha512（オプションアルゴリズム）
    with _engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(hash_records)")).fetchall()
        col_names = {r[1] for r in rows}
        if "sha512" not in col_names:
            conn.execute(
                text("ALTER TABLE hash_records ADD COLUMN sha512 VARCHAR(128) DEFAULT ''")
            )
            conn.commit()
            logger.info("マイグレーション: hash_records.sha512 を追加しました")

    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)

    logger.info(f"データベース初期化完了: {db_path}")


def get_session() -> Session:
    """新しいセッションを取得（手動で commit / close が必要な場合）"""
    if _session_factory is None:
        raise RuntimeError("データベースが初期化されていません。init_database() を先に呼び出してください。")
    return _session_factory()


@contextmanager
def session_scope():
    """トランザクション境界付きセッション（成功時 commit、例外時 rollback）"""
    if _session_factory is None:
        raise RuntimeError("データベースが初期化されていません。init_database() を先に呼び出してください。")
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


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
