"""Phase 3-2: error code registry"""
import re

from src.utils.error_codes import ALL_ERROR_CODES, category_for_code


class TestErrorCodes:
    def test_all_codes_unique(self):
        codes = list(ALL_ERROR_CODES.keys())
        assert len(codes) == len(set(codes))

    def test_format_e_four_digits(self):
        pat = re.compile(r"^E\d{4}$")
        for code in ALL_ERROR_CODES:
            assert pat.match(code), f"bad format: {code}"

    def test_category_for_code(self):
        assert category_for_code("E1001") == "system"
        assert category_for_code("E2001") == "device"
        assert category_for_code("E8001") == "optical_engine"
        assert category_for_code("") == "unknown"
