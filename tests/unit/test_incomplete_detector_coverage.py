"""incomplete_file_detector 追加カバレッジ"""
from src.utils.incomplete_file_detector import detect_incomplete_files


def test_empty_directory(tmp_path):
    result = detect_incomplete_files(str(tmp_path), ["*.dd"])
    assert result == []


def test_no_match(tmp_path):
    (tmp_path / "other.txt").write_text("hello")
    result = detect_incomplete_files(str(tmp_path), ["*.dd"])
    assert result == []


def test_detects_file(tmp_path):
    f = tmp_path / "image.dd"
    f.write_bytes(b"\x00" * 512)
    result = detect_incomplete_files(str(tmp_path), ["image*.dd"])
    assert len(result) == 1
    assert result[0]["size_bytes"] == 512
