"""DeviceWatcher のユニットテスト"""
from unittest.mock import MagicMock

from src.core.device_watcher import DeviceWatcher, reset_device_watcher_for_tests


def test_subscribe_and_notify():
    w = DeviceWatcher()
    cb = MagicMock()
    w.subscribe(cb)
    w._notify("arrival", {"drive_name": "E:"})
    cb.assert_called_once_with("arrival", {"drive_name": "E:"})


def test_unsubscribe():
    w = DeviceWatcher()
    cb = MagicMock()
    w.subscribe(cb)
    w.unsubscribe(cb)
    w._notify("removal", {})
    cb.assert_not_called()


def test_callback_error_does_not_propagate():
    w = DeviceWatcher()
    bad_cb = MagicMock(side_effect=RuntimeError("boom"))
    good_cb = MagicMock()
    w.subscribe(bad_cb)
    w.subscribe(good_cb)
    w._notify("arrival", {})
    good_cb.assert_called_once()


def test_stop_without_start():
    w = DeviceWatcher()
    w.stop()


def teardown_module():
    reset_device_watcher_for_tests()
