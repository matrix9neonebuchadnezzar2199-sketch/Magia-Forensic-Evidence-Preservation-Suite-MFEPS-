"""データベース初期化・マイグレーションのテスト"""

from sqlalchemy import text


class TestDatabaseInit:
    def test_init_creates_tables(self, tmp_path):
        from src.models.database import init_database, get_engine

        init_database(tmp_path / "init_test.db")
        engine = get_engine()
        with engine.connect() as conn:
            tables = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        table_names = {t[0] for t in tables}
        expected = {
            "cases",
            "evidence_items",
            "imaging_jobs",
            "hash_records",
            "chain_of_custody",
            "audit_log",
            "app_settings",
            "users",
        }
        assert expected.issubset(table_names)

    def test_wal_mode_enabled(self, tmp_path):
        from src.models.database import init_database, get_engine

        init_database(tmp_path / "wal_test.db")
        engine = get_engine()
        with engine.connect() as conn:
            mode = conn.execute(text("PRAGMA journal_mode")).fetchone()[0]
        assert mode.lower() == "wal"

    def test_migration_write_block_method(self, tmp_path):
        from src.models.database import init_database, get_engine

        init_database(tmp_path / "migrate_test.db")
        engine = get_engine()
        with engine.connect() as conn:
            cols = conn.execute(text("PRAGMA table_info(imaging_jobs)")).fetchall()
        col_names = {c[1] for c in cols}
        assert "write_block_method" in col_names
