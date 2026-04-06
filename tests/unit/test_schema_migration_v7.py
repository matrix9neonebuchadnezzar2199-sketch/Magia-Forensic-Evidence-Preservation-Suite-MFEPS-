"""schema_version 7 — users.is_active"""

from pathlib import Path

import sqlalchemy
from sqlalchemy import text

from src.models.database import get_engine, init_database


def test_migration_7_adds_is_active(tmp_path: Path):
    init_database(tmp_path / "mig7.db")
    engine = get_engine()
    inspector = sqlalchemy.inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("users")]
    assert "is_active" in columns


def test_schema_version_is_current(tmp_path: Path):
    init_database(tmp_path / "ver7.db")
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version FROM schema_version")).fetchone()
        assert row is not None
        assert int(row[0]) == 9
