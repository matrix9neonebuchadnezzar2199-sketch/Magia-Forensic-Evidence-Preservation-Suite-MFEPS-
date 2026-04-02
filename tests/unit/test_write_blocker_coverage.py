"""write_blocker の分岐（レジストリ・バッジ・デバイスチェックをモック）"""
from unittest.mock import MagicMock, patch

import src.core.write_blocker as wb


def test_enable_global_creates_key(monkeypatch):
    fake_key = object()
    monkeypatch.setattr(
        wb.winreg,
        "OpenKey",
        MagicMock(side_effect=FileNotFoundError()),
    )
    monkeypatch.setattr(wb.winreg, "CreateKey", MagicMock(return_value=fake_key))
    monkeypatch.setattr(wb.winreg, "SetValueEx", MagicMock())
    monkeypatch.setattr(wb.winreg, "CloseKey", MagicMock())
    assert wb.enable_global_write_block() is True


def test_disable_global_key_missing(monkeypatch):
    monkeypatch.setattr(
        wb.winreg,
        "OpenKey",
        MagicMock(side_effect=FileNotFoundError()),
    )
    assert wb.disable_global_write_block() is True


def test_is_global_write_blocked_missing():
    with patch.object(wb.winreg, "OpenKey", side_effect=FileNotFoundError()):
        assert wb.is_global_write_blocked() is False


def test_get_protection_badge_variants():
    assert wb.get_protection_badge(
        {"hardware_blocked": True, "registry_blocked": False, "is_protected": True}
    )[0] == "HW保護済"
    assert wb.get_protection_badge(
        {"hardware_blocked": False, "registry_blocked": True, "is_protected": True}
    )[0] == "SW保護済"
    assert wb.get_protection_badge(
        {"hardware_blocked": False, "registry_blocked": False, "is_protected": True}
    )[0] == "保護済"
    assert wb.get_protection_badge(
        {"hardware_blocked": False, "registry_blocked": False, "is_protected": False}
    )[0] == "未保護"


def test_check_write_protection_open_fails():
    with patch.object(wb, "is_global_write_blocked", return_value=False):
        with patch(
            "src.core.win32_raw_io.open_device",
            side_effect=OSError("no access"),
        ):
            r = wb.check_write_protection(r"\\.\PhysicalDrive99")
    assert r["registry_blocked"] is False
    assert r["is_protected"] is False


def test_verify_write_block_createfile_denied():
    k32 = MagicMock()
    k32.CreateFileW = MagicMock(return_value=-1)
    with patch.object(wb.ctypes, "windll", MagicMock(kernel32=k32)):
        assert wb.verify_write_block(r"\\.\PhysicalDrive0") is True


def test_verify_write_block_open_then_close():
    k32 = MagicMock()
    k32.CreateFileW = MagicMock(return_value=123)
    k32.CloseHandle = MagicMock()
    with patch.object(wb.ctypes, "windll", MagicMock(kernel32=k32)):
        assert wb.verify_write_block(r"\\.\PhysicalDrive0") is False
    k32.CloseHandle.assert_called_once_with(123)


def test_verify_write_block_exception():
    with patch.object(wb.ctypes, "windll", side_effect=RuntimeError("no windll")):
        assert wb.verify_write_block(r"\\.\X") is False
