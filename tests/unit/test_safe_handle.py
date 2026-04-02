"""SafeFileHandle / SafeDeviceHandle の冪等 close（Phase 5-1）"""
from unittest.mock import patch

import pytest

from src.utils.safe_handle import SafeDeviceHandle, SafeFileHandle


class TestSafeFileHandle:
    def test_write_and_close(self, tmp_path):
        p = tmp_path / "out.bin"
        f = open(p, "wb")
        sfh = SafeFileHandle(f)
        sfh.write(b"\x00" * 512)
        sfh.close()
        assert sfh.closed
        assert p.stat().st_size == 512

    def test_double_close_is_safe(self, tmp_path):
        sfh = SafeFileHandle(open(tmp_path / "out.bin", "wb"))
        sfh.close()
        sfh.close()
        assert sfh.closed

    def test_write_after_close_raises(self, tmp_path):
        sfh = SafeFileHandle(open(tmp_path / "out.bin", "wb"))
        sfh.close()
        with pytest.raises(ValueError, match="already closed"):
            sfh.write(b"x")

    def test_context_manager(self, tmp_path):
        p = tmp_path / "ctx.bin"
        with SafeFileHandle(open(p, "wb")) as sfh:
            sfh.write(b"ab")
        assert sfh.closed
        assert p.read_bytes() == b"ab"


class TestSafeDeviceHandle:
    @patch("src.utils.safe_handle.close_device")
    def test_close_calls_close_device(self, mock_close):
        sdh = SafeDeviceHandle(42, r"\\.\PhysicalDrive1")
        sdh.close()
        mock_close.assert_called_once_with(42)
        assert sdh.closed

    @patch("src.utils.safe_handle.close_device")
    def test_double_close_no_double_call(self, mock_close):
        sdh = SafeDeviceHandle(42, r"\\.\PhysicalDrive1")
        sdh.close()
        sdh.close()
        mock_close.assert_called_once()

    @patch("src.utils.safe_handle.close_device")
    def test_value_after_close_raises(self, mock_close):
        sdh = SafeDeviceHandle(42)
        sdh.close()
        with pytest.raises(ValueError, match="already closed"):
            _ = sdh.value
