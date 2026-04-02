"""db_backup 分岐"""
from unittest.mock import MagicMock, patch

from src.utils.db_backup import create_backup, list_backups


def test_create_backup_missing_db():
    with patch("src.utils.db_backup.get_config") as gc:
        cfg = MagicMock()
        p = MagicMock()
        p.exists.return_value = False
        cfg.db_path = p
        gc.return_value = cfg
        assert create_backup() is None


def test_create_backup_and_rotate(tmp_path):
    db = tmp_path / "live.db"
    db.write_bytes(b"sqlite3")
    backup_dir = tmp_path / "bk"
    with patch("src.utils.db_backup.get_config") as gc:
        cfg = MagicMock()
        cfg.db_path = db
        cfg.backup_dir = backup_dir
        gc.return_value = cfg
        out = create_backup("unit")
    assert out is not None
    assert out.is_file()


def test_list_backups_no_dir():
    with patch("src.utils.db_backup.get_config") as gc:
        cfg = MagicMock()
        bd = MagicMock()
        bd.exists.return_value = False
        cfg.backup_dir = bd
        gc.return_value = cfg
        assert list_backups() == []


def test_create_backup_copy_oserror(tmp_path):
    db = tmp_path / "live.db"
    db.write_bytes(b"x")
    with patch("src.utils.db_backup.get_config") as gc:
        cfg = MagicMock()
        cfg.db_path = db
        cfg.backup_dir = tmp_path / "bk"
        gc.return_value = cfg
        with patch("src.utils.db_backup.shutil.copy2", side_effect=OSError("denied")):
            assert create_backup() is None


def test_list_backups_non_empty(tmp_path):
    bd = tmp_path / "backups"
    bd.mkdir()
    (bd / "mfeps_old.db").write_bytes(b"1")
    with patch("src.utils.db_backup.get_config") as gc:
        cfg = MagicMock()
        cfg.backup_dir = bd
        gc.return_value = cfg
        rows = list_backups()
    assert len(rows) == 1
    assert rows[0]["filename"] == "mfeps_old.db"


def test_backup_rotation_keeps_max_five(tmp_path):
    db = tmp_path / "live.db"
    db.write_bytes(b"x")
    bd = tmp_path / "bkrot"
    bd.mkdir()
    with patch("src.utils.db_backup.get_config") as gc:
        cfg = MagicMock()
        cfg.db_path = db
        cfg.backup_dir = bd
        gc.return_value = cfg
        for i in range(7):
            create_backup(f"rot{i}")
    assert len(list(bd.glob("mfeps_*.db"))) == 5
