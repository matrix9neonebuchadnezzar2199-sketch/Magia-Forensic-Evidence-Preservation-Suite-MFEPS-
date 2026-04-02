"""user_settings ペイロード・永続化の追加テスト"""

from src.utils.user_settings import (
    apply_user_settings_to_environ,
    merge_file_into_storage,
    persist_user_settings_from_storage,
    user_settings_path,
)


def test_persist_includes_syslog_and_audit(tmp_path):
    stored = {
        "output_dir": "./out",
        "font_size": 16,
        "theme": "dark",
        "rfc3161_enabled": False,
        "tsa_url": "http://x",
        "double_read": False,
        "buffer_label": "1 MiB",
        "syslog_host": "10.0.0.1",
        "syslog_port": 5514,
        "syslog_proto": "tcp",
        "audit_jsonl_enabled": True,
        "audit_jsonl_path": "logs/a.jsonl",
        "locale": "en",
    }
    defaults = {
        "output_dir": "./output",
        "font_size": 16,
        "theme": "dark",
        "rfc3161_enabled": False,
        "tsa_url": "http://timestamp.digicert.com",
        "double_read": False,
        "ewfacquire_path": "",
        "ewfverify_path": "",
        "buffer_label": "1 MiB",
        "syslog_host": "",
        "syslog_port": 514,
        "syslog_proto": "udp",
        "audit_jsonl_enabled": False,
        "audit_jsonl_path": "logs/audit_export.jsonl",
    }
    persist_user_settings_from_storage(
        stored,
        data_dir=tmp_path,
        config_defaults=defaults,
    )
    raw = user_settings_path(tmp_path).read_text(encoding="utf-8")
    assert "MFEPS_SYSLOG_HOST" in raw
    assert "10.0.0.1" in raw
    assert "MFEPS_AUDIT_JSONL_ENABLED" in raw


def test_merge_restores_locale(tmp_path):
    p = user_settings_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '{"ui": {"locale": "en", "hash_md5": true}, "environment": {}}',
        encoding="utf-8",
    )
    stored: dict = {}
    merge_file_into_storage(stored, tmp_path)
    assert stored.get("locale") == "en"


def test_apply_user_settings_flat_legacy(tmp_path, monkeypatch):
    p = user_settings_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '{"MFEPS_OUTPUT_DIR": "./x", "MFEPS_FONT_SIZE": "18"}',
        encoding="utf-8",
    )
    monkeypatch.delenv("MFEPS_OUTPUT_DIR", raising=False)
    apply_user_settings_to_environ(tmp_path)
    import os
    assert os.environ.get("MFEPS_OUTPUT_DIR") == "./x"
