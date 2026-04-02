"""DoubleBufferManager pause / resume（Phase 4-3）"""
import asyncio
import io

import pytest

from src.core.buffer_manager import DoubleBufferManager
from src.core.hash_engine import TripleHashEngine


class TestBufferPauseResume:
    def test_pause_blocks_read_until_timeout(self):
        buf_size = 2048
        total = buf_size * 4

        def fake_read(offset, size, _buf):
            return b"\x01" * min(size, total - offset)

        mgr = DoubleBufferManager(buffer_size=buf_size, sector_size=2048)
        cancel = asyncio.Event()
        pause = asyncio.Event()
        pause.clear()

        async def run():
            read_task = asyncio.create_task(
                mgr.read_loop(fake_read, total, cancel, pause)
            )
            await asyncio.sleep(0.02)
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(read_task, timeout=1.0)
            cancel.set()
            pause.set()
            try:
                await read_task
            except asyncio.CancelledError:
                pass

        asyncio.run(run())

    def test_resume_completes_read(self):
        buf_size = 2048
        total = buf_size * 2
        data = b"\x02" * total

        def fake_read(offset, size, _buf):
            return data[offset : offset + size]

        mgr = DoubleBufferManager(buffer_size=buf_size, sector_size=2048)
        hash_eng = TripleHashEngine(md5=True, sha1=False, sha256=False)
        cancel = asyncio.Event()
        pause = asyncio.Event()
        pause.clear()

        async def run():
            read_task = asyncio.create_task(
                mgr.read_loop(fake_read, total, cancel, pause)
            )
            await asyncio.sleep(0.05)
            pause.set()
            processed = await mgr.process_loop(hash_eng, io.BytesIO())
            await read_task
            return processed

        processed = asyncio.run(run())
        assert processed == total

    def test_cancel_after_pause_stops_loop(self):
        buf_size = 2048
        total = 10_000_000

        def fake_read(_o, size, _buf):
            return b"\x00" * size

        mgr = DoubleBufferManager(buffer_size=buf_size, sector_size=2048)
        cancel = asyncio.Event()
        pause = asyncio.Event()
        pause.clear()

        async def run():
            read_task = asyncio.create_task(
                mgr.read_loop(fake_read, total, cancel, pause)
            )
            await asyncio.sleep(0.05)
            cancel.set()
            pause.set()
            await asyncio.wait_for(read_task, timeout=3.0)

        asyncio.run(run())
