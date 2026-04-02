"""セッション有効期限テスト"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


def test_session_valid_within_timeout():
    now = datetime.now(timezone.utc)
    storage = {"user_id": "u1", "login_at": now.isoformat(), "role": "admin"}
    mock_app = MagicMock()
    mock_app.storage.user = storage
    with patch("src.ui.session_auth.app", mock_app), patch(
        "src.ui.session_auth.get_config"
    ) as mcfg:
        mcfg.return_value.session_timeout_hours = 8
        from src.ui.session_auth import check_session_valid

        assert check_session_valid() is True


def test_session_expired():
    expired = datetime.now(timezone.utc) - timedelta(hours=9)
    storage = {
        "user_id": "u1",
        "login_at": expired.isoformat(),
        "role": "admin",
    }
    mock_app = MagicMock()
    mock_app.storage.user = storage
    with patch("src.ui.session_auth.app", mock_app), patch(
        "src.ui.session_auth.get_config"
    ) as mcfg:
        mcfg.return_value.session_timeout_hours = 8
        from src.ui.session_auth import check_session_valid

        assert check_session_valid() is False
    assert storage == {}


def test_session_no_login_at():
    storage = {"user_id": "u1", "role": "admin"}
    mock_app = MagicMock()
    mock_app.storage.user = storage
    with patch("src.ui.session_auth.app", mock_app):
        from src.ui.session_auth import check_session_valid

        assert check_session_valid() is False


def test_session_clear_on_expire():
    expired = datetime.now(timezone.utc) - timedelta(days=1)
    storage = {
        "user_id": "x",
        "login_at": expired.isoformat(),
    }
    mock_app = MagicMock()
    mock_app.storage.user = storage
    with patch("src.ui.session_auth.app", mock_app), patch(
        "src.ui.session_auth.get_config"
    ) as mcfg:
        mcfg.return_value.session_timeout_hours = 1
        from src.ui.session_auth import check_session_valid

        assert check_session_valid() is False
    assert storage == {}
