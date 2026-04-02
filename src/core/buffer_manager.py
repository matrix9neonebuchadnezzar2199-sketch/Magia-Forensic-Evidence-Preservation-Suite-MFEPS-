"""
MFEPS v2.1.0 — ダブルバッファリング管理
読取と処理（ハッシュ+書込）をオーバーラップさせてスループット最大化
"""
import asyncio
import concurrent.futures
import ctypes
import logging
import sys
from typing import Callable, Optional

logger = logging.getLogger("mfeps.buffer_manager")


class DoubleBufferManager:
    """
    ダブルバッファリングパイプライン。
    Buffer A: [読取中] → [処理待ち] → [処理中] → [読取中] → ...
    Buffer B: [処理中] → [読取中] → [処理待ち] → [処理中] → ...
    """

    def __init__(self, buffer_size: int = 1_048_576, sector_size: int = 512):
        if buffer_size % sector_size != 0:
            raise ValueError(
                f"バッファサイズ({buffer_size})はセクタサイズ({sector_size})の倍数でなければなりません"
            )

        self.buffer_size = buffer_size
        self.sector_size = sector_size
        self._buffer_a = ctypes.create_string_buffer(buffer_size)
        self._buffer_b = ctypes.create_string_buffer(buffer_size)
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=2)
        self._error_count = 0
        self._error_sectors: list[int] = []
        self._read_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="mfeps-read"
        )
        self._write_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="mfeps-write"
        )

        logger.info(
            f"ダブルバッファ初期化: size={buffer_size}, sector={sector_size}")

    async def read_loop(
        self,
        read_func: Callable,
        total_bytes: int,
        cancel_event: asyncio.Event,
        pause_event: asyncio.Event,
    ) -> None:
        """
        非同期読取ループ。
        read_func(offset, size, buffer) -> bytes を呼び出してキューに投入。
        buffer は ctypes バッファ（read_sectors 等にそのまま渡す）。
        """
        offset = 0
        use_a = True

        while offset < total_bytes:
            # キャンセルチェック
            if cancel_event.is_set():
                await self._queue.put(None)  # 終了シグナル
                return

            # 一時停止チェック
            await pause_event.wait()

            # 読取サイズ計算
            remaining = total_bytes - offset
            read_size = min(self.buffer_size, remaining)

            # セクタアラインメント
            if read_size % self.sector_size != 0:
                read_size = ((read_size // self.sector_size) + 1) * self.sector_size

            # 読取実行（ダブルバッファを交互に使用）
            try:
                buf = self._buffer_a if use_a else self._buffer_b
                data = await asyncio.get_running_loop().run_in_executor(
                    self._read_executor, read_func, offset, read_size, buf,
                )
                if not data:
                    break

                # 実際に必要なバイト数にトリミング
                actual_size = min(len(data), remaining)
                if actual_size < len(data):
                    data = data[:actual_size]

                await self._queue.put((offset, data))
                offset += len(data)
                use_a = not use_a

            except OSError as e:
                logger.warning(f"読取エラー offset={offset}: {e}")
                self._error_count += 1
                self._error_sectors.append(offset // self.sector_size)

                # ゼロフィル
                zero_data = b'\x00' * read_size
                actual_size = min(len(zero_data), remaining)
                await self._queue.put((offset, zero_data[:actual_size]))
                offset += actual_size
                use_a = not use_a

        # 終了シグナル
        await self._queue.put(None)
        logger.debug(f"読取ループ完了: offset={offset}")

    async def process_loop(
        self,
        hash_engine,
        output_file,
        progress_callback: Optional[Callable] = None,
    ) -> int:
        """
        非同期処理ループ。
        キューからデータを取得し、ハッシュ更新→ファイル書込を実行。
        Returns: 処理した総バイト数
        """
        total_processed = 0

        while True:
            item = await self._queue.get()

            if item is None:
                break  # 終了シグナル

            offset, data = item

            # ハッシュ更新
            hash_engine.update(data)

            # ファイル書込（非同期）
            await asyncio.get_running_loop().run_in_executor(
                self._write_executor, output_file.write, data
            )

            total_processed += len(data)

            # 進捗コールバック
            if progress_callback:
                try:
                    progress_callback(total_processed)
                except Exception as e:
                    logger.warning(f"進捗コールバックエラー: {e}")

        logger.debug(f"処理ループ完了: {total_processed} bytes")
        return total_processed

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def error_sectors(self) -> list[int]:
        return self._error_sectors.copy()

    def reset(self) -> None:
        """エラーカウンタリセット"""
        self._error_count = 0
        self._error_sectors.clear()
        self._queue = asyncio.Queue(maxsize=2)

    def shutdown(self) -> None:
        """既定スレッドプール枯渇を避けるため専用 Executor を終了"""
        _kw: dict = {"wait": False}
        if sys.version_info >= (3, 9):
            _kw["cancel_futures"] = True
        self._read_executor.shutdown(**_kw)
        self._write_executor.shutdown(**_kw)
