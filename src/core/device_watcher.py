"""
MFEPS v2.2.0 — USB ストレージ着脱検知
バックグラウンドでブロックデバイス一覧をポーリングし、変化時にコールバックする。
（WMI イベントは環境差が大きいため、確実な差分検出に統一）
"""
import logging
import sys
import threading
from typing import Callable, Optional

logger = logging.getLogger("mfeps.device_watcher")


class DeviceWatcher:
    """デバイスパス集合の変化を監視しコールバックする。"""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._callbacks: list[Callable[[str, dict], None]] = []
        self._lock = threading.Lock()
        self._poll_interval_sec = 3.0

    def subscribe(self, callback: Callable[[str, dict], None]) -> None:
        """callback(event_type, info) — event_type は arrival | removal"""
        with self._lock:
            self._callbacks.append(callback)

    def unsubscribe(self, callback: Callable) -> None:
        with self._lock:
            self._callbacks = [c for c in self._callbacks if c is not callback]

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.debug("DeviceWatcher は既に稼働中")
            return
        if sys.platform != "win32":
            logger.info("DeviceWatcher: Windows 以外では未起動")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._watch_loop, daemon=True, name="DeviceWatcher"
        )
        self._thread.start()
        logger.info("DeviceWatcher 開始")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("DeviceWatcher 停止")

    def _watch_loop(self) -> None:
        prev_paths: set[str] = set()
        first = True
        while not self._stop_event.is_set():
            try:
                from src.core.device_detector import detect_block_devices

                devices = detect_block_devices()
                curr = {d.device_path for d in devices}
                if not first:
                    for p in curr - prev_paths:
                        self._notify(
                            "arrival",
                            {"drive_name": p, "event_type_code": 2},
                        )
                    for p in prev_paths - curr:
                        self._notify(
                            "removal",
                            {"drive_name": p, "event_type_code": 3},
                        )
                first = False
                prev_paths = curr
            except Exception as e:
                if self._stop_event.is_set():
                    break
                logger.warning("デバイスポーリングエラー: %s", e)
            self._stop_event.wait(self._poll_interval_sec)

    def _notify(self, event_type: str, info: dict) -> None:
        drive = info.get("drive_name", "")
        logger.info("デバイスイベント: %s drive=%s", event_type, drive)
        with self._lock:
            cbs = list(self._callbacks)
        for cb in cbs:
            try:
                cb(event_type, info)
            except Exception as e:
                logger.warning("DeviceWatcher コールバックエラー: %s", e)


_watcher: Optional[DeviceWatcher] = None
_watcher_lock = threading.Lock()


def get_device_watcher() -> DeviceWatcher:
    global _watcher
    if _watcher is not None:
        return _watcher
    with _watcher_lock:
        if _watcher is None:
            _watcher = DeviceWatcher()
    return _watcher


def reset_device_watcher_for_tests() -> None:
    global _watcher
    with _watcher_lock:
        if _watcher is not None:
            _watcher.stop()
        _watcher = None
