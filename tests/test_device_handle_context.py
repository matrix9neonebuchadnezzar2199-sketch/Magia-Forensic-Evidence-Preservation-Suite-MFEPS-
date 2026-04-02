"""device_handle context manager (Phase 2-2)"""
from unittest.mock import patch

import pytest


class TestDeviceHandleContext:
    def test_closes_after_success(self):
        with patch(
            "src.core.win32_raw_io.open_device", return_value=99
        ) as op, patch(
            "src.core.win32_raw_io.close_device"
        ) as cl:
            from src.core.win32_raw_io import device_handle

            with device_handle(r"\\.\E:") as h:
                assert h == 99
            op.assert_called_once_with(r"\\.\E:")
            cl.assert_called_once_with(99)

    def test_closes_after_block_exception(self):
        with patch(
            "src.core.win32_raw_io.open_device", return_value=101
        ), patch(
            "src.core.win32_raw_io.close_device"
        ) as cl:
            from src.core.win32_raw_io import device_handle

            with pytest.raises(RuntimeError, match="boom"):
                with device_handle(r"\\.\D:"):
                    raise RuntimeError("boom")
            cl.assert_called_once_with(101)

    def test_open_failure_no_close(self):
        with patch(
            "src.core.win32_raw_io.open_device",
            side_effect=OSError("no device"),
        ), patch(
            "src.core.win32_raw_io.close_device"
        ) as cl:
            from src.core.win32_raw_io import device_handle

            with pytest.raises(OSError, match="no device"):
                with device_handle(r"\\.\Z:"):
                    pass
            cl.assert_not_called()
