"""全登録エラーコードの参照・カテゴリ整合"""
from __future__ import annotations

import pytest

from src.utils.error_codes import ALL_ERROR_CODES, category_for_code, get_error


@pytest.mark.parametrize("code", sorted(ALL_ERROR_CODES.keys()))
def test_get_error_roundtrip(code: str):
    ec = get_error(code)
    assert ec is not None
    assert ec.code == code
    d = ec.to_dict()
    assert d["code"] == code
    assert d["severity"] in ("WARN", "ERROR", "CRITICAL")


@pytest.mark.parametrize("code", sorted(ALL_ERROR_CODES.keys()))
def test_category_non_unknown(code: str):
    cat = category_for_code(code)
    assert cat != "unknown"
