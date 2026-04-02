"""incomplete_file_reporting カバレッジ"""
from src.models.database import init_database
from src.utils.incomplete_file_reporting import (
    append_incomplete_files_report,
    incomplete_reason_from_job_status,
)


def test_append_empty_records_returns_unchanged(tmp_path):
    init_database(tmp_path / "ifr.db")
    assert append_incomplete_files_report("j", "r", [], None) == ""
    assert append_incomplete_files_report("j", "r", [], "note") == "note"


def test_append_with_records(tmp_path):
    init_database(tmp_path / "ifr2.db")
    rec = [{"path": "/x", "size_bytes": 1, "modified_at": "t"}]
    out = append_incomplete_files_report("jid-1", "failed", rec, "")
    assert "incomplete_files" in out
    out2 = append_incomplete_files_report("jid-1", "failed", rec, "prev")
    assert out2.startswith("prev\n")


def test_incomplete_reason_from_status():
    assert incomplete_reason_from_job_status("cancelled") == "cancelled"
    assert incomplete_reason_from_job_status("failed") == "failed"
    assert incomplete_reason_from_job_status("other") == "failed"
