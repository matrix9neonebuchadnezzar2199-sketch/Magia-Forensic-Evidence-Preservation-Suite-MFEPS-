"""folder_manager のユニットテスト"""

from src.utils.folder_manager import ensure_project_structure


def test_ensure_project_structure_creates_dirs(tmp_path):
    base = tmp_path / "proj"
    base.mkdir()
    ensure_project_structure(base)
    for name in (
        "data",
        "output",
        "logs",
        "reports",
        "templates",
        "backup",
        "libs",
    ):
        assert (base / name).is_dir()


def test_ensure_project_structure_idempotent(tmp_path):
    base = tmp_path / "p"
    base.mkdir()
    ensure_project_structure(base)
    ensure_project_structure(base)
    assert (base / "data").is_dir()
