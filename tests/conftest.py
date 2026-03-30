"""pytest 共通フィクスチャ"""
import pytest


@pytest.fixture
def audit_service(tmp_path):
    """一時 SQLite で AuditService を構築"""
    from src.models.database import init_database
    from src.services.audit_service import AuditService

    init_database(tmp_path / "audit_test.db")
    return AuditService()
