"""schema_version 8 — imaging_jobs.remote_agent_id"""

from pathlib import Path

import sqlalchemy
from sqlalchemy import text

from src.models.database import get_engine, init_database


def test_migration_8_adds_remote_agent_id(tmp_path: Path):
    init_database(tmp_path / "mig8.db")
    engine = get_engine()
    inspector = sqlalchemy.inspect(engine)
    columns = [c["name"] for c in inspector.get_columns("imaging_jobs")]
    assert "remote_agent_id" in columns


def test_schema_version_is_8(tmp_path: Path):
    init_database(tmp_path / "ver8.db")
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version FROM schema_version")).fetchone()
        assert row is not None
        assert int(row[0]) == 8
