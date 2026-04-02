"""E9xxx エラーコード"""

from src.utils.error_codes import ALL_ERROR_CODES, category_for_code, get_error


def test_e9001_exists():
    e = get_error("E9001")
    assert e is not None
    assert e.severity.value == "ERROR"


def test_e9_category():
    assert category_for_code("E9001") == "user"


def test_all_e9_codes():
    e9 = [k for k in ALL_ERROR_CODES if k.startswith("E9")]
    assert len(e9) >= 3
