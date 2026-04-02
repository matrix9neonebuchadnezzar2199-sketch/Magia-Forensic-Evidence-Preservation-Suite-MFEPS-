"""audit_service 追加分岐"""
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.models.database import init_database
from src.services.audit_service import AuditService, _audit_timestamp_iso


def test_audit_timestamp_iso_naive():
    ts = datetime(2024, 1, 15, 12, 0, 0)
    out = _audit_timestamp_iso(ts)
    assert "+00:00" in out or "UTC" in out or "T" in out


def test_verify_chain_empty(tmp_path):
    init_database(tmp_path / "aud1.db")
    svc = AuditService()
    r = svc.verify_chain()
    assert r["valid"] is True
    assert r["total_entries"] == 0


def test_verify_chain_valid(tmp_path):
    init_database(tmp_path / "aud2.db")
    svc = AuditService()
    svc.add_entry("INFO", "system", "one")
    svc.add_entry("INFO", "system", "two")
    r = svc.verify_chain()
    assert r["valid"] is True
    assert r["total_entries"] == 2


def test_get_entries_filtered(tmp_path):
    init_database(tmp_path / "aud3.db")
    svc = AuditService()
    svc.add_entry("WARN", "imaging", "w")
    rows = svc.get_entries(limit=10, level="WARN")
    assert len(rows) == 1
    assert rows[0]["level"] == "WARN"


def test_export_log_csv(tmp_path):
    init_database(tmp_path / "aud4.db")
    svc = AuditService()
    svc.add_entry("INFO", "system", "csv-test")
    csv_data = svc.export_log(format="csv")
    assert "csv-test" in csv_data
    assert "INFO" in csv_data


def test_add_entry_db_error_swallowed():
    with patch("src.services.audit_service.session_scope") as sc:
        cm = MagicMock()
        cm.__enter__.side_effect = RuntimeError("db down")
        sc.return_value = cm
        AuditService().add_entry("INFO", "system", "x")


def test_add_entry_exporter_raises_debug(tmp_path):
    init_database(tmp_path / "aud5.db")
    ex = MagicMock()
    ex.export.side_effect = OSError("no export")

    with patch("src.utils.audit_exporter.get_audit_exporter", return_value=ex):
        AuditService().add_entry("INFO", "system", "with-export")
