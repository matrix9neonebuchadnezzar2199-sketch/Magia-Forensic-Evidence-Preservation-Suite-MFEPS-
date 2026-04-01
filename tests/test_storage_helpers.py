"""storage_helpers — NiceGUI 未初期化時のフォールバック"""
import sys
import types

import pytest


@pytest.fixture
def fake_nicegui_no_app(monkeypatch):
    """nicegui はあるが app が無い状態 → from nicegui import app が失敗"""
    old = sys.modules.pop("nicegui", None)
    fake = types.ModuleType("nicegui")
    sys.modules["nicegui"] = fake
    try:
        yield
    finally:
        if old is not None:
            sys.modules["nicegui"] = old
        else:
            del sys.modules["nicegui"]


def test_get_general_storage_without_app(fake_nicegui_no_app):
    from src.utils.storage_helpers import get_general_storage

    assert get_general_storage() == {}


def test_get_storage_value_without_app_returns_default(fake_nicegui_no_app):
    from src.utils.storage_helpers import get_storage_value

    assert get_storage_value("ewfacquire_path", "x") == "x"
    assert get_storage_value("missing") is None


def test_get_storage_value_explicit_default(fake_nicegui_no_app):
    from src.utils.storage_helpers import get_storage_value

    assert get_storage_value("k", default=42) == 42


def test_get_user_storage_without_app(fake_nicegui_no_app):
    from src.utils.storage_helpers import get_user_storage

    assert get_user_storage() == {}
