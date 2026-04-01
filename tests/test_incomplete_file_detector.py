"""incomplete_file_detector 単体テスト"""
from pathlib import Path

from src.utils.incomplete_file_detector import detect_incomplete_files


class TestDetectIncompleteFiles:
    def test_detect_existing_files(self, tmp_path: Path) -> None:
        d = tmp_path / "out"
        d.mkdir()
        f = d / "image.dd"
        f.write_bytes(b"x" * 100)

        rows = detect_incomplete_files(str(d), ["image.dd"])
        assert len(rows) == 1
        assert rows[0]["path"] == str(f.resolve())
        assert rows[0]["size_bytes"] == 100
        assert len(rows[0]["modified_at"]) >= 10

    def test_detect_e01_segments(self, tmp_path: Path) -> None:
        d = tmp_path / "e01out"
        d.mkdir()
        (d / "image.E01").write_text("a")
        (d / "image.E02").write_text("bb")

        rows = detect_incomplete_files(str(d), ["image.E*"])
        paths = {r["path"] for r in rows}
        assert len(paths) == 2
        assert sum(r["size_bytes"] for r in rows) == 3

    def test_empty_directory(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        assert detect_incomplete_files(str(d), ["image.dd"]) == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        assert (
            detect_incomplete_files(str(tmp_path / "nope"), ["image.dd"]) == []
        )

    def test_dedupe_glob_and_literal(self, tmp_path: Path) -> None:
        d = tmp_path / "o"
        d.mkdir()
        f = d / "image.dd"
        f.write_bytes(b"ab")
        rows = detect_incomplete_files(str(d), ["image.dd", "image.dd"])
        assert len(rows) == 1
        assert rows[0]["size_bytes"] == 2
