"""pytest 共通フィクスチャ"""
import os

import pytest

# テスト中に実際の DB パスを汚染しないようにする
os.environ.setdefault("MFEPS_OUTPUT_DIR", "./test_output")
os.environ.setdefault("MFEPS_LOG_LEVEL", "DEBUG")


@pytest.fixture
def audit_service(tmp_path):
    """一時 SQLite で AuditService を構築"""
    from src.models.database import init_database
    from src.services.audit_service import AuditService

    init_database(tmp_path / "audit_test.db")
    return AuditService()


@pytest.fixture
def fresh_db(tmp_path):
    """クリーンな一時 DB を初期化して返す"""
    from src.models.database import init_database

    db_path = tmp_path / "test.db"
    init_database(db_path)
    return db_path
