"""progress_broadcaster カバレッジ"""
import asyncio

import pytest

from src.services.progress_broadcaster import (
    get_broadcaster,
    reset_broadcaster_for_tests,
)


class _BrokenQueue:
    """QueueFull 後の get_nowait / put_nowait で失敗させ購読者を除去する"""

    def put_nowait(self, _msg):
        raise asyncio.QueueFull

    def get_nowait(self):
        raise RuntimeError("broken client")

    def empty(self):
        return True


@pytest.fixture(autouse=True)
def _reset_broadcaster():
    reset_broadcaster_for_tests()
    yield
    reset_broadcaster_for_tests()


def test_publish_and_get_latest():
    async def _run():
        b = get_broadcaster()
        await b.publish("j1", {"percent": 50.0})
        assert b.get_latest("j1") == {"percent": 50.0}

    asyncio.run(_run())


def test_subscribe_receive():
    async def _run():
        b = get_broadcaster()
        q = b.subscribe("c1")
        await b.publish("j1", {"x": 1})
        msg = await asyncio.wait_for(q.get(), timeout=2.0)
        assert msg["job_id"] == "j1"
        assert msg["x"] == 1

    asyncio.run(_run())


def test_queue_full_drops_old():
    async def _run():
        b = get_broadcaster()
        q = b.subscribe("c1")
        for i in range(100):
            q.put_nowait({"job_id": "old", "i": i})
        await b.publish("j1", {"fresh": True})
        assert b.get_latest("j1") == {"fresh": True}
        found = False
        while not q.empty():
            msg = q.get_nowait()
            if msg.get("job_id") == "j1":
                found = True
                assert msg["fresh"] is True
        assert found

    asyncio.run(_run())


def test_clear_job():
    async def _run():
        b = get_broadcaster()
        await b.publish("jx", {"p": 1})

    asyncio.run(_run())
    b = get_broadcaster()
    b.clear_job("jx")
    assert b.get_latest("jx") is None


def test_unsubscribe():
    b = get_broadcaster()
    b.subscribe("z")
    b.unsubscribe("z")
    assert "z" not in b._subscribers


def test_publish_removes_dead_subscriber():
    async def _run():
        b = get_broadcaster()
        b._subscribers["dead"] = _BrokenQueue()
        await b.publish("jdead", {"v": 1})
        assert "dead" not in b._subscribers

    asyncio.run(_run())
