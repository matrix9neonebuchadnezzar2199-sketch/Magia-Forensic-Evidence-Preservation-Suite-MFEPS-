"""Phase 3-1: imaging_engine exception paths"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.core.imaging_engine import ImagingEngine, ImagingJobParams


def _job(tmp_path):
    return ImagingJobParams(
        job_id="j1",
        evidence_id="e1",
        case_id="c1",
        source_path=r"\\.\PhysicalDrive9",
        output_dir=str(tmp_path / "out"),
        verify_after_copy=False,
    )


def test_open_device_oserror_sets_e2005(tmp_path):
    async def _run():
        eng = ImagingEngine()
        with patch(
            "src.core.imaging_engine.open_device",
            side_effect=OSError("denied"),
        ):
            return await eng.execute(_job(tmp_path))

    r = asyncio.run(_run())
    assert r.status == "failed"
    assert r.error_code == "E2005"


def test_geometry_oserror_sets_e2006(tmp_path):
    async def _run():
        eng = ImagingEngine()
        with patch("src.core.imaging_engine.open_device", return_value=42), patch(
            "src.core.imaging_engine.get_disk_geometry",
            side_effect=OSError("geom"),
        ), patch("src.core.imaging_engine.close_device"):
            return await eng.execute(_job(tmp_path))

    r = asyncio.run(_run())
    assert r.status == "failed"
    assert r.error_code == "E2006"


def test_cancelled_error_propagates(tmp_path):
    async def _run():
        eng = ImagingEngine()
        du = MagicMock()
        du.free = 10**15

        with patch("src.core.imaging_engine.open_device", return_value=3), patch(
            "src.core.imaging_engine.get_disk_geometry",
            return_value={"bytes_per_sector": 512},
        ), patch("src.core.imaging_engine.get_disk_length", return_value=1024), patch(
            "src.core.imaging_engine.verify_write_block", return_value=True
        ), patch("src.core.imaging_engine.psutil.disk_usage", return_value=du), patch(
            "builtins.open", MagicMock()
        ), patch(
            "asyncio.gather", side_effect=asyncio.CancelledError
        ):
            with pytest.raises(asyncio.CancelledError):
                await eng.execute(_job(tmp_path))

    asyncio.run(_run())


def test_unexpected_exception_sets_failed(tmp_path):
    async def _run():
        eng = ImagingEngine()
        with patch(
            "src.core.imaging_engine.open_device",
            side_effect=RuntimeError("x"),
        ):
            return await eng.execute(_job(tmp_path))

    r = asyncio.run(_run())
    assert r.status == "failed"
    assert "予期せぬ" in (r.error_message or "")


def test_pipeline_oserror_e1003(tmp_path):
    async def _run():
        eng = ImagingEngine()
        du = MagicMock()
        du.free = 10**15

        async def fake_gather(*_a, **_k):
            raise OSError("pipeline")

        with patch("src.core.imaging_engine.open_device", return_value=3), patch(
            "src.core.imaging_engine.get_disk_geometry",
            return_value={"bytes_per_sector": 512},
        ), patch("src.core.imaging_engine.get_disk_length", return_value=1024), patch(
            "src.core.imaging_engine.verify_write_block", return_value=True
        ), patch("src.core.imaging_engine.psutil.disk_usage", return_value=du), patch(
            "builtins.open", MagicMock()
        ), patch("asyncio.gather", fake_gather):
            return await eng.execute(_job(tmp_path))

    r = asyncio.run(_run())
    assert r.status == "failed"
    assert r.error_code == "E1003"
