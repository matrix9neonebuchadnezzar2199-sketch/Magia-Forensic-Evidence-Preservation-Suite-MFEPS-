"""schema_version 9 — 検索用インデックス"""

from pathlib import Path

import sqlalchemy
from sqlalchemy import text

from src.models.database import get_engine, init_database


def test_migration_9_adds_query_indexes(tmp_path: Path):
    init_database(tmp_path / "mig9.db")
    engine = get_engine()
    inspector = sqlalchemy.inspect(engine)
    names = {ix["name"] for ix in inspector.get_indexes("hash_records")}
    assert "ix_hash_records_job_id" in names
    assert "ix_hash_records_job_target" in names
    names_ij = {ix["name"] for ix in inspector.get_indexes("imaging_jobs")}
    assert "ix_imaging_jobs_evidence_id" in names_ij
    names_coc = {ix["name"] for ix in inspector.get_indexes("chain_of_custody")}
    assert "ix_chain_of_custody_evidence_id" in names_coc


def test_schema_version_is_9(tmp_path: Path):
    init_database(tmp_path / "ver9b.db")
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version FROM schema_version")).fetchone()
        assert row is not None
        assert int(row[0]) == 9
