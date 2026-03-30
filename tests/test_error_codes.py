"""エラーコード体系のテスト"""

from src.utils.error_codes import Severity


def test_all_error_codes_have_required_fields():
    from src.utils.error_codes import ALL_ERROR_CODES

    for code, err in ALL_ERROR_CODES.items():
        assert err.code == code
        assert err.message_en, f"{code} has no English message"
        assert err.message_ja, f"{code} has no Japanese message"
        assert err.severity in (
            Severity.WARN,
            Severity.ERROR,
            Severity.CRITICAL,
        ), f"{code} invalid severity"


def test_get_error_returns_correct_code():
    from src.utils.error_codes import get_error

    e = get_error("E1001")
    assert e is not None
    assert e.code == "E1001"


def test_get_error_returns_none_for_unknown():
    from src.utils.error_codes import get_error

    assert get_error("E9999") is None
