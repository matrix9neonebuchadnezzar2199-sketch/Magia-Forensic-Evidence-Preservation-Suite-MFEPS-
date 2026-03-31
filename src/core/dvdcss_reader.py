# SPDX-License-Identifier: MIT
#
# This module optionally imports pydvdcss (GPL-3.0).
# When pydvdcss is not installed, all functionality in this module
# is disabled and MFEPS falls back to RAW (encrypted) sector reading.
# MFEPS does not bundle or redistribute pydvdcss.

"""
MFEPS v2.1.0 — pydvdcss 復号リーダー
CSS 暗号化 DVD の論理ブロック（2048 バイト）単位の復号読取

PyPI の pydvdcss（libdvdcss の ctypes ラッパー）の実 API:
  open(target)         → int（ハンドル、失敗時は -1）
  seek(lba, flags)     → int（新 LBA、エラー時は負値）
  read(blocks, flags)  → bytes（復号済みデータ。内部でバッファに格納後スライスして返す）
  is_scrambled()       → bool
  close() / dispose()  → 解放

フラグ（libdvdcss / pydvdcss.DvdCss と同一値）:
  NO_FLAGS       = 0
  READ_DECRYPT   = 1   read() 時: スクランブル復号
  SEEK_MPEG      = 1   seek() 時: MPEG/VOB シーク
  SEEK_KEY       = 2   seek() 時: タイトルキー取得
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("mfeps.dvdcss_reader")

SECTOR_SIZE = 2048

DVDCSS_NO_FLAGS = 0
DVDCSS_READ_DECRYPT = 1
DVDCSS_SEEK_MPEG = 1
DVDCSS_SEEK_KEY = 2


class DvdCssReader:
    """
    pydvdcss 経由の復号リーダー。optical_engine のイメージングループから利用する。

    利用例::
        reader = DvdCssReader()
        reader.open("D:")
        data = reader.read_sectors(lba, count, is_title_start=True)
        reader.close()
    """

    def __init__(self) -> None:
        self._dvd: Optional[object] = None
        self._drive_path: str = ""
        self._is_scrambled: bool = False
        self._current_lba: int = 0

    def open(self, drive_path: str) -> bool:
        """
        DVD をオープンし、スクランブル状態を確認する。
        pydvdcss が未インストールの場合は ImportError を送出する。
        """
        try:
            from pydvdcss import DvdCss
        except ImportError:
            logger.error(
                "pydvdcss が見つかりません。"
                "pip install pydvdcss でインストールしてください。"
            )
            raise

        self._dvd = DvdCss()
        handle = self._dvd.open(drive_path)
        if handle < 0:
            try:
                self._dvd.dispose()
            except Exception:
                pass
            self._dvd = None
            raise OSError(
                "pydvdcss オープン失敗（デバイスパス・libdvdcss を確認）"
            )

        self._drive_path = drive_path
        self._is_scrambled = self._dvd.is_scrambled()
        self._current_lba = 0
        logger.info(
            "DvdCssReader オープン: %s, scrambled=%s",
            drive_path,
            self._is_scrambled,
        )
        return True

    @property
    def is_scrambled(self) -> bool:
        """CSS スクランブルの有無を返す。open() 後に呼び出すこと。"""
        if self._dvd is None:
            raise OSError("DVD デバイスが開かれていません")
        return self._dvd.is_scrambled()

    def read_sectors(
        self,
        lba: int,
        sector_count: int,
        *,
        is_title_start: bool = False,
    ) -> bytes:
        """
        LBA 位置から指定ブロック数を復号読取する。

        Phase 1 ではディスク先頭チャンクのみ ``is_title_start=True``（SEEK_KEY）。
        将来的に VTS 境界テーブル解析で精密化可能。
        """
        if self._dvd is None:
            raise RuntimeError("DvdCssReader が未オープンです")

        dvd = self._dvd
        seek_flags = dvd.SEEK_KEY if is_title_start else dvd.SEEK_MPEG

        result_lba = dvd.seek(lba, seek_flags)
        if result_lba < 0:
            raise OSError(
                f"pydvdcss シーク失敗: LBA={lba}, "
                f"flags={'SEEK_KEY' if is_title_start else 'SEEK_MPEG'}, "
                f"error={dvd.error()!r}"
            )

        read_flags = dvd.READ_DECRYPT if self._is_scrambled else dvd.NO_FLAGS

        # pydvdcss.read は復号済み bytes を返す（.buffer 属性は使用しない）
        data = dvd.read(sector_count, read_flags)
        self._current_lba = lba + sector_count

        expected_len = sector_count * SECTOR_SIZE
        if len(data) < expected_len:
            logger.warning(
                "部分読取: LBA=%s requested_blocks=%s got_bytes=%s (expected %s)",
                lba,
                sector_count,
                len(data),
                expected_len,
            )

        return data

    def close(self) -> None:
        """リソース解放。未オープンでも安全。"""
        if self._dvd is not None:
            try:
                self._dvd.close()
                self._dvd.dispose()
                logger.info("DvdCssReader クローズ完了")
            except Exception as e:
                logger.warning("DvdCssReader クローズエラー: %s", e)
            finally:
                self._dvd = None
                self._is_scrambled = False
                self._current_lba = 0

    def __enter__(self) -> "DvdCssReader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
