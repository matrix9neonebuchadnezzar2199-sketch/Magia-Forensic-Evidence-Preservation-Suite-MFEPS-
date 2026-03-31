"""DoubleBufferManager の EOF ガード・基本動作テスト"""
import asyncio
import io

from src.core.buffer_manager import DoubleBufferManager
from src.core.hash_engine import TripleHashEngine


class TestDoubleBufferManager:
    def test_normal_read_write(self):
        buf_size = 512
        total = 1024
        test_data = b"A" * 512 + b"B" * 512

        def fake_read(offset, size, _buf):
            return test_data[offset: offset + size]

        mgr = DoubleBufferManager(buffer_size=buf_size, sector_size=512)
        hash_eng = TripleHashEngine(md5=True, sha1=False, sha256=False)
        output = io.BytesIO()
        cancel = asyncio.Event()
        pause = asyncio.Event()
        pause.set()

        async def run_once():
            read_task = asyncio.create_task(
                mgr.read_loop(fake_read, total, cancel, pause)
            )
            processed = await mgr.process_loop(hash_eng, output)
            await read_task
            return processed

        processed = asyncio.run(run_once())
        assert processed == total
        assert output.getvalue() == test_data

    def test_eof_guard_empty_return(self):
        call_count = 0

        def fake_read_eof(_offset, size, _buf):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"X" * size
            return b""

        mgr = DoubleBufferManager(buffer_size=512, sector_size=512)
        hash_eng = TripleHashEngine(md5=True, sha1=False, sha256=False)
        output = io.BytesIO()
        cancel = asyncio.Event()
        pause = asyncio.Event()
        pause.set()

        async def run_once():
            read_task = asyncio.create_task(
                mgr.read_loop(fake_read_eof, 10_000_000, cancel, pause)
            )
            processed = await mgr.process_loop(hash_eng, output)
            await read_task
            return processed

        processed = asyncio.run(run_once())
        assert processed == 512
        assert call_count == 2

    def test_cancel_event(self):
        def fake_read(_offset, size, _buf):
            return b"\x00" * size

        mgr = DoubleBufferManager(buffer_size=512, sector_size=512)
        hash_eng = TripleHashEngine(md5=True, sha1=False, sha256=False)
        output = io.BytesIO()
        cancel = asyncio.Event()
        pause = asyncio.Event()
        pause.set()
        cancel.set()

        async def run_once():
            read_task = asyncio.create_task(
                mgr.read_loop(fake_read, 10_000_000, cancel, pause)
            )
            processed = await mgr.process_loop(hash_eng, output)
            await read_task
            return processed

        processed = asyncio.run(run_once())
        assert processed == 0
