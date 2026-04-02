"""進捗ブロードキャスター単体テスト"""
import asyncio

from src.services.progress_broadcaster import ProgressBroadcaster


def test_subscribe_and_receive():
    async def _run():
        b = ProgressBroadcaster()
        q = b.subscribe("c1")
        await b.publish("j1", {"status": "imaging", "percent": 50.0})
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["job_id"] == "j1"
        assert msg["percent"] == 50.0

    asyncio.run(_run())


def test_unsubscribe():
    async def _run():
        b = ProgressBroadcaster()
        b.subscribe("c1")
        b.unsubscribe("c1")
        await b.publish("j1", {"x": 1})

    asyncio.run(_run())


def test_queue_full_drops_oldest():
    async def _run():
        b = ProgressBroadcaster()
        q = asyncio.Queue(maxsize=2)
        b._subscribers["c1"] = q
        for n in range(5):
            await b.publish("j", {"n": n})
        assert q.qsize() <= 2

    asyncio.run(_run())


def test_get_latest():
    async def _run():
        b = ProgressBroadcaster()
        await b.publish("j1", {"p": 1})
        assert b.get_latest("j1") == {"p": 1}

    asyncio.run(_run())


def test_clear_job():
    async def _run():
        b = ProgressBroadcaster()
        await b.publish("j1", {"p": 1})
        b.clear_job("j1")
        assert b.get_latest("j1") is None

    asyncio.run(_run())
