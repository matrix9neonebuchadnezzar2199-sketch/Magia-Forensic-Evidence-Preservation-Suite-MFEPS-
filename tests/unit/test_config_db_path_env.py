"""MFEPS_DB_PATH による DB パス上書き"""
from __future__ import annotations

from pathlib import Path


def test_mfeps_db_path_env_override(monkeypatch, tmp_path: Path):
    db = tmp_path / "custom.db"
    monkeypatch.setenv("MFEPS_DB_PATH", str(db))

    import src.utils.config as cfg

    cfg.reload_config()
    assert cfg.get_config().db_path.resolve() == db.resolve()


def test_mfeps_db_path_relative_to_base(monkeypatch):
    monkeypatch.setenv("MFEPS_DB_PATH", "data/rel_custom.db")

    import src.utils.config as cfg

    cfg.reload_config()
    p = cfg.get_config().db_path
    assert p.name == "rel_custom.db"
    assert p.is_absolute()
