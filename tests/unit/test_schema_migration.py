"""スキーマバージョン・マイグレーション"""
from sqlalchemy import text

from src.models.database import get_engine, init_database


def test_migration_idempotent(tmp_path):
    p = tmp_path / "twice.db"
    init_database(p)
    init_database(p)
    with get_engine().connect() as c:
        row = c.execute(
            text("SELECT version FROM schema_version WHERE id = 1")
        ).fetchone()
    assert row is not None
    assert int(row[0]) == 8


def test_schema_version_increments(fresh_db):
    from sqlalchemy import text

    with get_engine().connect() as c:
        row = c.execute(
            text("SELECT version FROM schema_version WHERE id = 1")
        ).fetchone()
    assert row is not None
    assert int(row[0]) == 8
