# SPDX-License-Identifier: MIT
#
# This module optionally loads libaacs (LGPL-2.1-or-later) via ctypes.
# libaacs is not bundled with MFEPS. Users must provide libaacs.dll
# and keydb.cfg separately. LGPL-2.1 dynamic linking is compatible
# with the MIT License.

"""
MFEPS v2.0 — libaacs 復号リーダー（ctypes）
AACS 暗号化 BD のセクタ単位復号読取

keydb.cfg が無い、または DLL が無い場合は open が False を返し RAW にフォールバックする。
実際の libaacs のエクスポート名はビルドにより異なる場合があるため、
aacs_open2 / aacs_open を順に試す。
"""
from __future__ import annotations

import ctypes
import logging
import os
from ctypes import c_char_p, c_int, c_void_p
from pathlib import Path
from typing import Optional

from src.utils.config import get_config

logger = logging.getLogger("mfeps.aacs_reader")

SECTOR_SIZE = 2048


def _resolve_path(p: str) -> Path:
    path = Path(p)
    if not path.is_absolute():
        path = get_config().base_dir / path
    return path.resolve()


class AacsReader:
    """libaacs 経由の AACS 復号リーダー。"""

    def __init__(self) -> None:
        self._lib: Optional[ctypes.CDLL] = None
        self._handle: Optional[int] = None
        self._drive_path: str = ""
        self._mkb_version: int = 0
        self._available: bool = False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def mkb_version(self) -> int:
        return self._mkb_version

    def open(self, drive_path: str) -> bool:
        """
        BD をオープンし AACS 復号を試みる。
        DLL / keydb 不足時は False（例外にしない）。
        """
        config = get_config()
        dll_path = _resolve_path(config.aacs_library)
        keydb_path = (
            _resolve_path(config.aacs_keydb_path)
            if config.aacs_keydb_path
            else None
        )

        if not dll_path.exists():
            logger.info("libaacs DLL 未検出: %s — AACS復号スキップ", dll_path)
            self._available = False
            return False

        if not keydb_path or not keydb_path.exists():
            logger.info(
                "AACS keydb.cfg 未検出 — AACS復号スキップ"
            )
            self._available = False
            return False

        os.environ.setdefault("KEYDB_CFG_FILE", str(keydb_path))

        try:
            self._lib = ctypes.CDLL(str(dll_path))
            self._bind_symbols()
        except OSError as e:
            logger.warning("libaacs DLL ロード失敗: %s", e)
            self._available = False
            self._lib = None
            return False
        except Exception as e:
            logger.warning("libaacs シンボル解決失敗: %s", e)
            self._available = False
            self._lib = None
            return False

        key_b = str(keydb_path).encode("utf-8")
        dev_b = drive_path.encode("utf-8")

        self._handle = self._fn_open(dev_b, key_b)
        if not self._handle:
            logger.warning("libaacs オープン失敗（キー不足またはデバイスエラー）")
            self._available = False
            self._lib = None
            return False

        self._drive_path = drive_path
        self._mkb_version = self._get_mkb_safe()
        self._available = True
        logger.info(
            "AacsReader オープン: %s, MKB version=%s",
            drive_path,
            self._mkb_version,
        )
        return True

    def _bind_symbols(self) -> None:
        lib = self._lib
        assert lib is not None

        if hasattr(lib, "aacs_open2"):
            lib.aacs_open2.argtypes = [c_char_p, c_char_p]
            lib.aacs_open2.restype = c_void_p
            self._fn_open = lib.aacs_open2
        elif hasattr(lib, "aacs_open"):
            lib.aacs_open.argtypes = [c_char_p, c_char_p]
            lib.aacs_open.restype = c_void_p
            self._fn_open = lib.aacs_open
        else:
            raise OSError("libaacs に aacs_open / aacs_open2 が見つかりません")

        if not hasattr(lib, "aacs_read"):
            raise OSError("libaacs に aacs_read が見つかりません")

        lib.aacs_read.argtypes = [
            c_void_p,
            ctypes.c_char_p,
            c_int,
            c_int,
        ]
        lib.aacs_read.restype = c_int

        if hasattr(lib, "aacs_get_mkb_version"):
            lib.aacs_get_mkb_version.argtypes = [c_void_p]
            lib.aacs_get_mkb_version.restype = c_int

        lib.aacs_close.argtypes = [c_void_p]
        lib.aacs_close.restype = None

    def _get_mkb_safe(self) -> int:
        lib = self._lib
        if not lib or not self._handle:
            return 0
        if not hasattr(lib, "aacs_get_mkb_version"):
            return 0
        try:
            return int(lib.aacs_get_mkb_version(self._handle))
        except Exception:
            return 0

    def read_sectors(self, lba: int, sector_count: int) -> bytes:
        if not self._available or not self._handle or not self._lib:
            raise RuntimeError("AacsReader が未オープンまたは利用不可です")

        buf_size = sector_count * SECTOR_SIZE
        buf = ctypes.create_string_buffer(buf_size)
        n = self._lib.aacs_read(
            self._handle, buf, int(lba), int(sector_count)
        )
        if n < 0:
            raise OSError(
                f"libaacs 読取失敗: LBA={lba}, sectors={sector_count}"
            )
        # 返り値は読み取ったセクタ数と仮定
        out_bytes = min(buf_size, max(0, n) * SECTOR_SIZE)
        return buf.raw[:out_bytes]

    def close(self) -> None:
        if self._handle and self._lib:
            try:
                self._lib.aacs_close(self._handle)
                logger.info("AacsReader クローズ完了")
            except Exception as e:
                logger.warning("AacsReader クローズエラー: %s", e)
            finally:
                self._handle = None
                self._lib = None
                self._available = False

    def __enter__(self) -> "AacsReader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
