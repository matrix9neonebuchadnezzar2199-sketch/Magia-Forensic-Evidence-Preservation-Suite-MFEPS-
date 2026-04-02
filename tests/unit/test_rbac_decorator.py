"""require_role デコレータの挙動"""
import asyncio
from unittest.mock import patch

from src.utils.rbac import require_role


def test_require_role_sync_allows():
    @require_role("examiner")
    def fn():
        return 42

    with patch("src.utils.rbac.has_permission", return_value=True):
        assert fn() == 42


def test_require_role_sync_blocks():
    @require_role("examiner")
    def fn():
        return 42

    with patch("src.utils.rbac.has_permission", return_value=False), patch(
        "src.utils.rbac.ui.notify"
    ) as n:
        assert fn() is None
        n.assert_called_once()


def test_require_role_async_allows():
    @require_role("admin")
    async def fn():
        return "ok"

    async def _run():
        with patch("src.utils.rbac.has_permission", return_value=True):
            return await fn()

    assert asyncio.run(_run()) == "ok"


def test_require_role_async_blocks():
    @require_role("admin")
    async def fn():
        return "ok"

    async def _run():
        with patch("src.utils.rbac.has_permission", return_value=False), patch(
            "src.utils.rbac.ui.notify"
        ) as n:
            r = await fn()
            n.assert_called_once()
            return r

    assert asyncio.run(_run()) is None
