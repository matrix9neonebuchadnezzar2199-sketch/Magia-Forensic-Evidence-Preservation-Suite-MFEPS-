"""
MFEPS v2.1.0 — SafeFileHandle / SafeDeviceHandle
二重クローズ防止ラッパー
"""
import logging
from typing import BinaryIO

from src.core.win32_raw_io import close_device

logger = logging.getLogger("mfeps.safe_handle")


class SafeFileHandle:
    """
    Python ファイルオブジェクトを包み、close() を冪等にする。
    with 文にも対応。
    """

    def __init__(self, file_obj: BinaryIO):
        self._file = file_obj
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def raw(self) -> BinaryIO:
        """内部ファイルオブジェクトを直接取得（read/write / fileno 用）"""
        if self._closed:
            raise ValueError("SafeFileHandle is already closed")
        return self._file

    def write(self, data: bytes) -> int:
        if self._closed:
            raise ValueError("SafeFileHandle is already closed")
        return self._file.write(data)

    def flush(self) -> None:
        if not self._closed:
            self._file.flush()

    def fileno(self) -> int:
        if self._closed:
            raise ValueError("SafeFileHandle is already closed")
        return self._file.fileno()

    def close(self) -> None:
        if self._closed:
            logger.debug("SafeFileHandle.close(): 既にクローズ済み — スキップ")
            return
        try:
            self._file.close()
        except Exception as e:
            logger.warning("SafeFileHandle.close() 例外: %s", e)
        finally:
            self._closed = True

    def __enter__(self) -> "SafeFileHandle":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class SafeDeviceHandle:
    """
    Win32 デバイスハンドル (int) を包み、close_device() を冪等にする。
    """

    def __init__(self, handle: int, path: str = ""):
        self._handle = handle
        self._path = path
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def value(self) -> int:
        """生ハンドル値を返す。クローズ済みなら ValueError。"""
        if self._closed:
            raise ValueError(
                f"SafeDeviceHandle for '{self._path}' is already closed"
            )
        return self._handle

    def close(self) -> None:
        if self._closed:
            logger.debug(
                "SafeDeviceHandle.close(): '%s' 既にクローズ済み — スキップ",
                self._path,
            )
            return
        try:
            close_device(self._handle)
        except Exception as e:
            logger.warning("SafeDeviceHandle.close() 例外: %s", e)
        finally:
            self._closed = True

    def __enter__(self) -> "SafeDeviceHandle":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
