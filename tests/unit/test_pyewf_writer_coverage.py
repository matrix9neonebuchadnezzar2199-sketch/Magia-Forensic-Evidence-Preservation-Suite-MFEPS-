"""pyewf_writer 追加カバレッジ"""
import asyncio
import sys
from unittest.mock import MagicMock

import pytest

from src.core.e01_writer import E01Params
from src.core.pyewf_writer import (
    PyEWFWriter,
    get_pyewf_version,
    is_pyewf_available,
)


def test_pyewf_availability_is_bool():
    assert isinstance(is_pyewf_available(), bool)


def test_get_version_returns_str():
    v = get_pyewf_version()
    assert isinstance(v, str)


def test_cancel_before_acquire():
    async def _run():
        w = PyEWFWriter()
        await w.cancel()
        params = E01Params(source_path=r"\\.\PhysicalDrive99", output_dir="./out")
        with pytest.MonkeyPatch.context() as mp:
            mp.setitem(sys.modules, "pyewf", MagicMock())
            return await w.acquire(params)

    result = asyncio.run(_run())
    assert result.error_code == "E3006"


def test_get_progress_default():
    w = PyEWFWriter()
    p = w.get_progress()
    assert p["status"] == "idle"
    assert p["percent"] == 0.0
