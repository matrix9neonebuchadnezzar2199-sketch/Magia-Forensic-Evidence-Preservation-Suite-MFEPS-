"""pyewf フォールバック"""
import asyncio
import builtins
import sys
from unittest.mock import MagicMock

from src.core.e01_writer import E01Params, E01Writer
from src.core.pyewf_writer import PyEWFWriter, get_pyewf_version, is_pyewf_available


def test_is_pyewf_available_returns_bool():
    assert isinstance(is_pyewf_available(), bool)


def test_get_pyewf_version_string():
    assert isinstance(get_pyewf_version(), str)


def test_check_available_has_pyewf_keys():
    d = E01Writer.check_available()
    assert "pyewf_available" in d
    assert "pyewf_version" in d


def test_acquire_cancel(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyewf", MagicMock())

    async def _run():
        w = PyEWFWriter()
        await w.cancel()
        p = E01Params(source_path=r"\\.\X", output_dir=".", output_basename="t")
        r = await w.acquire(p)
        assert r.error_code == "E3006"

    asyncio.run(_run())


def test_acquire_pyewf_not_installed(monkeypatch):
    real_import = builtins.__import__

    def _imp(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pyewf":
            raise ImportError("no pyewf")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _imp)

    async def _run():
        w = PyEWFWriter()
        p = E01Params(source_path=r"\\.\X", output_dir=".", output_basename="t")
        r = await w.acquire(p)
        assert r.error_code == "E7001"

    asyncio.run(_run())
