"""DB バックアップユーティリティテスト"""
from pathlib import Path


from src.utils.db_backup import create_backup, list_backups


def test_create_backup_success(monkeypatch, tmp_path: Path):
    db_file = tmp_path / "mfeps.db"
    db_file.write_bytes(b"sqlite-test")

    backup_root = tmp_path / "backup"

    class C:
        db_path = db_file
        backup_dir = backup_root

    monkeypatch.setattr("src.utils.db_backup.get_config", lambda: C())
    out = create_backup(reason="unit")
    assert out is not None
    assert out.exists()
    assert out.read_bytes() == b"sqlite-test"


def test_create_backup_no_db(monkeypatch, tmp_path: Path):
    class C:
        db_path = tmp_path / "missing.db"
        backup_dir = tmp_path / "backup"

    monkeypatch.setattr("src.utils.db_backup.get_config", lambda: C())
    assert create_backup() is None


def test_rotate_backups(monkeypatch, tmp_path: Path):
    import os
    import time

    from src.utils import db_backup as mod

    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    base = time.time()
    for i in range(6):
        p = backup_dir / f"mfeps_old_{i}.db"
        p.write_bytes(b"x")
        os.utime(p, (base - i, base - i))
    monkeypatch.setattr(mod, "_MAX_BACKUPS", 5)
    mod._rotate_backups(backup_dir)
    assert len(list(backup_dir.glob("mfeps_*.db"))) <= 5


def test_list_backups(monkeypatch, tmp_path: Path):
    backup_root = tmp_path / "backup"
    backup_root.mkdir()
    p = backup_root / "mfeps_x.db"
    p.write_bytes(b"ab")

    class C:
        backup_dir = backup_root

    monkeypatch.setattr("src.utils.db_backup.get_config", lambda: C())
    rows = list_backups()
    assert len(rows) == 1
    assert rows[0]["filename"] == "mfeps_x.db"
    assert rows[0]["size_bytes"] == 2
