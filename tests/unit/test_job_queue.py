"""ジョブキュー単体テスト"""
import asyncio

from src.core.job_queue import JobPriority, JobQueue, QueuedJobStatus


def test_submit_and_complete():
    async def _run():
        jq = JobQueue(max_concurrent=2)
        try:
            done = []

            async def work():
                await asyncio.sleep(0.01)
                done.append(1)

            _, t = await jq.submit("j1", work, JobPriority.NORMAL)
            await t
            assert done == [1]
            st = jq.get_status("j1")
            assert st and st["status"] == QueuedJobStatus.COMPLETED.value
        finally:
            await jq.aclose()

    asyncio.run(_run())


def test_concurrent_limit():
    async def _run():
        q = JobQueue(max_concurrent=1)
        try:
            ev = asyncio.Event()
            order = []

            async def a():
                order.append("a_start")
                await ev.wait()
                order.append("a_end")

            async def b():
                order.append("b")

            _, ta = await q.submit("a", a, JobPriority.NORMAL)
            await asyncio.sleep(0)
            _, tb = await q.submit("b", b, JobPriority.NORMAL)
            await asyncio.sleep(0)
            assert "a_start" in order
            assert "b" not in order
            ev.set()
            await asyncio.gather(ta, tb)
            assert order.index("a_end") < order.index("b")
        finally:
            await q.aclose()

    asyncio.run(_run())


def test_cancel_queued_job():
    async def _run():
        jq = JobQueue(max_concurrent=1)
        try:
            ev1 = asyncio.Event()
            ev2 = asyncio.Event()

            async def j1():
                await ev1.wait()

            async def j2():
                await ev2.wait()

            _, t1 = await jq.submit("x", j1, JobPriority.NORMAL)
            await asyncio.sleep(0)
            await jq.submit("y", j2, JobPriority.NORMAL)
            await asyncio.sleep(0)
            ok = await jq.cancel_job("y")
            assert ok
            ev1.set()
            await t1
            st = jq.get_status("y")
            assert st and st["status"] == QueuedJobStatus.CANCELLED.value
        finally:
            await jq.aclose()

    asyncio.run(_run())


def test_list_jobs():
    async def _run():
        jq = JobQueue(max_concurrent=2)
        try:
            async def w():
                await asyncio.sleep(0.01)

            await jq.submit("a", w, JobPriority.NORMAL)
            jobs = jq.list_jobs(limit=10)
            assert len(jobs) >= 1
            assert any(j["job_id"] == "a" for j in jobs)
        finally:
            await jq.aclose()

    asyncio.run(_run())


def test_cleanup_completed():
    async def _run():
        jq = JobQueue(max_concurrent=2)
        try:
            async def w():
                await asyncio.sleep(0.01)

            _, t = await jq.submit("c1", w, JobPriority.NORMAL)
            await t
            n = await jq.cleanup_completed(max_age_seconds=-1)
            assert n >= 1
            assert jq.get_status("c1") is None
        finally:
            await jq.aclose()

    asyncio.run(_run())


def test_priority_ordering():
    async def _run():
        q = JobQueue(max_concurrent=1)
        try:
            order = []

            async def mark(name: str):
                order.append(f"{name}_start")
                await asyncio.sleep(0.02)
                order.append(f"{name}_end")

            _, th = await q.submit("hi", lambda: mark("H"), JobPriority.HIGH)
            _, tn = await q.submit("no", lambda: mark("N"), JobPriority.NORMAL)
            await asyncio.gather(th, tn)
            assert order.index("H_start") < order.index("N_start")
        finally:
            await q.aclose()

    asyncio.run(_run())
