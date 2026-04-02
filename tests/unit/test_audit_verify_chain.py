"""監査ハッシュチェーン検証テスト"""
import hashlib
from datetime import datetime

import pytest

from src.models.database import init_database, session_scope
from src.models.schema import AuditLog
from src.services.audit_service import AuditService
from src.utils.constants import GENESIS_HASH_INPUT


@pytest.fixture
def audit_db(tmp_path):
    init_database(tmp_path / "audit_chain.db")
    return tmp_path


def test_verify_empty_chain(audit_db):
    svc = AuditService()
    r = svc.verify_chain()
    assert r["valid"] is True
    assert r["total_entries"] == 0


def test_verify_valid_chain(audit_db):
    ts_iso = "2026-01-01T12:00:00+00:00"
    genesis = hashlib.sha256(GENESIS_HASH_INPUT.encode()).hexdigest()
    h1 = hashlib.sha256(
        f"{genesis}|{ts_iso}|INFO|A|m1|".encode()
    ).hexdigest()
    h2 = hashlib.sha256(
        f"{h1}|{ts_iso}|INFO|B|m2|".encode()
    ).hexdigest()
    ts_db = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    with session_scope() as s:
        s.add(
            AuditLog(
                timestamp=ts_db,
                hash_timestamp_iso=ts_iso,
                level="INFO",
                category="A",
                message="m1",
                detail="",
                prev_hash=genesis,
                entry_hash=h1,
            )
        )
        s.add(
            AuditLog(
                timestamp=ts_db,
                hash_timestamp_iso=ts_iso,
                level="INFO",
                category="B",
                message="m2",
                detail="",
                prev_hash=h1,
                entry_hash=h2,
            )
        )
    svc = AuditService()
    r = svc.verify_chain()
    assert r["valid"] is True
    assert r["total_entries"] == 2


def test_verify_tampered_chain(audit_db):
    genesis = hashlib.sha256(GENESIS_HASH_INPUT.encode()).hexdigest()
    ts_iso = "2026-01-01T12:00:00+00:00"
    ts_db = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    bad_hash = "0" * 64
    with session_scope() as s:
        s.add(
            AuditLog(
                timestamp=ts_db,
                hash_timestamp_iso=ts_iso,
                level="INFO",
                category="A",
                message="m",
                detail="",
                prev_hash=genesis,
                entry_hash=bad_hash,
            )
        )
    svc = AuditService()
    r = svc.verify_chain()
    assert r["valid"] is False
