"""
MFEPS v2.1.0 — SQLite データベース接続・初期化
WALモード, 自動テーブル生成
"""
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

from src.models.schema import Base

logger = logging.getLogger("mfeps.database")

_engine = None
_session_factory = None

_SCHEMA_VERSION = 6  # Phase 6 時点


def _ensure_schema_version_table(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            "  id INTEGER PRIMARY KEY DEFAULT 1,"
            "  version INTEGER NOT NULL DEFAULT 0,"
            "  updated_at TEXT DEFAULT ''"
            ")"
        ))
        row = conn.execute(
            text("SELECT version FROM schema_version WHERE id = 1")
        ).fetchone()
        if row is None:
            conn.execute(text(
                "INSERT INTO schema_version (id, version, updated_at) "
                "VALUES (1, 0, '')"
            ))
        conn.commit()


def _get_schema_version(engine: Engine) -> int:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT version FROM schema_version WHERE id = 1")
        ).fetchone()
        return int(row[0]) if row else 0


def _set_schema_version(engine: Engine, version: int) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with engine.connect() as conn:
        conn.execute(text(
            "UPDATE schema_version SET version = :v, updated_at = :t WHERE id = 1"
        ), {"v": version, "t": ts})
        conn.commit()


def _migration_1_imaging_write_block(engine: Engine) -> None:
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(imaging_jobs)")).fetchall()
        col_names = {r[1] for r in rows}
        if "write_block_method" not in col_names:
            conn.execute(
                text(
                    "ALTER TABLE imaging_jobs ADD COLUMN write_block_method "
                    "VARCHAR(20) DEFAULT 'none'"
                )
            )
            logger.info("マイグレーション: imaging_jobs.write_block_method を追加しました")
        conn.commit()


def _migration_2_audit_hash_timestamp(engine: Engine) -> None:
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(audit_log)")).fetchall()
        col_names = {r[1] for r in rows}
        if "hash_timestamp_iso" not in col_names:
            conn.execute(
                text(
                    "ALTER TABLE audit_log ADD COLUMN hash_timestamp_iso "
                    "VARCHAR(64) DEFAULT ''"
                )
            )
            conn.commit()
            logger.info("マイグレーション: audit_log.hash_timestamp_iso を追加しました")


def _migration_3_hash_sha512(engine: Engine) -> None:
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(hash_records)")).fetchall()
        col_names = {r[1] for r in rows}
        if "sha512" not in col_names:
            conn.execute(
                text(
                    "ALTER TABLE hash_records ADD COLUMN sha512 VARCHAR(128) DEFAULT ''"
                )
            )
            conn.commit()
            logger.info("マイグレーション: hash_records.sha512 を追加しました")


def _migration_4_evidence_unique_index(engine: Engine) -> None:
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_case_number "
                    "ON evidence_items (case_id, evidence_number)"
                )
            )
            conn.commit()
            logger.info(
                "マイグレーション: evidence_items.uq_evidence_case_number を確認しました"
            )
    except Exception as e:
        logger.warning(
            "evidence_items 一意インデックスを作成できませんでした: %s",
            e,
        )


def _migration_5_e01_columns(engine: Engine) -> None:
    e01_new_columns = {
        "e01_compression": "VARCHAR(40) DEFAULT ''",
        "e01_segment_size_bytes": "INTEGER DEFAULT 0",
        "e01_ewf_format": "VARCHAR(20) DEFAULT ''",
        "e01_examiner_name": "VARCHAR(200) DEFAULT ''",
        "e01_notes": "TEXT DEFAULT ''",
        "e01_command_line": "TEXT DEFAULT ''",
        "e01_ewfacquire_version": "VARCHAR(100) DEFAULT ''",
        "e01_segment_count": "INTEGER DEFAULT 0",
        "e01_log_path": "VARCHAR(500) DEFAULT ''",
    }
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(imaging_jobs)")).fetchall()
        col_names = {r[1] for r in rows}
        for col_name, col_def in e01_new_columns.items():
            if col_name not in col_names:
                conn.execute(
                    text(
                        f"ALTER TABLE imaging_jobs ADD COLUMN {col_name} {col_def}"
                    )
                )
                logger.info(
                    "マイグレーション: imaging_jobs.%s を追加しました", col_name
                )
        conn.commit()


def _migration_6_noop(_engine: Engine) -> None:
    """schema_version テーブルは _ensure_schema_version_table で用意済み。"""
    pass


_MIGRATIONS: dict[int, Callable[[Engine], None]] = {
    1: _migration_1_imaging_write_block,
    2: _migration_2_audit_hash_timestamp,
    3: _migration_3_hash_sha512,
    4: _migration_4_evidence_unique_index,
    5: _migration_5_e01_columns,
    6: _migration_6_noop,
}


def _run_migrations(engine: Engine) -> None:
    _ensure_schema_version_table(engine)
    current = _get_schema_version(engine)
    for ver in range(current + 1, _SCHEMA_VERSION + 1):
        fn = _MIGRATIONS.get(ver)
        if fn is None:
            logger.warning("未定義のマイグレーション版: %s", ver)
            continue
        fn(engine)
        _set_schema_version(engine, ver)
        logger.info("スキーマをバージョン %s に更新しました", ver)


def init_database(db_path: Path) -> None:
    """データベースを初期化"""
    global _engine, _session_factory

    if _engine is not None:
        _engine.dispose()
        _engine = None
        _session_factory = None

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

    _run_migrations(_engine)

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
