"""監査ログ外部転送テスト"""
import json

from src.utils.audit_exporter import AuditExporter


def test_jsonl_export(tmp_path):
    jsonl = tmp_path / "audit.jsonl"
    exp = AuditExporter(jsonl_path=jsonl)
    exp.export("INFO", "TEST", "message1", "", "hash1", "prev1")
    exp.export("WARN", "TEST", "message2", "detail", "hash2", "hash1")

    lines = jsonl.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["level"] == "INFO"
    assert first["entry_hash"] == "hash1"


def test_jsonl_creates_parent(tmp_path):
    deep = tmp_path / "a" / "b" / "audit.jsonl"
    exp = AuditExporter(jsonl_path=deep)
    exp.export("INFO", "T", "m", "", "h", "p")
    assert deep.exists()


def test_syslog_init_invalid_host():
    exp = AuditExporter(syslog_host="192.0.2.1", syslog_port=9999)
    exp.export("INFO", "T", "m", "", "h", "p")


def test_no_export_when_disabled():
    exp = AuditExporter()
    exp.export("INFO", "T", "m", "", "h", "p")


def test_close():
    exp = AuditExporter()
    exp.close()
