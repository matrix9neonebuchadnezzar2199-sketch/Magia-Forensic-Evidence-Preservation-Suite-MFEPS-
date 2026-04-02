"""Phase 3-1: DoubleBufferManager edge cases"""
import asyncio

from src.core.buffer_manager import DoubleBufferManager


def test_read_oserror_increments_error_count():
    async def _run():
        mgr = DoubleBufferManager(buffer_size=512, sector_size=512)
        cancel = asyncio.Event()
        pause = asyncio.Event()
        pause.set()

        def read_func(off, sz, buf):
            raise OSError("read fail")

        # キュー詰まり回避のため 1 バッファ分のみ（process_loop なし）
        await mgr.read_loop(read_func, 512, cancel, pause)
        return mgr

    mgr = asyncio.run(_run())
    assert mgr.error_count >= 1


def test_cancel_stops_read_loop():
    async def _run():
        mgr = DoubleBufferManager(buffer_size=512, sector_size=512)
        cancel = asyncio.Event()
        cancel.set()
        pause = asyncio.Event()
        pause.set()

        def read_func(off, sz, buf):
            return b"\x00" * sz

        await mgr.read_loop(read_func, 512, cancel, pause)
        return mgr

    mgr = asyncio.run(_run())
    assert mgr.error_count == 0

