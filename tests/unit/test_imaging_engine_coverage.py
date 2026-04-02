"""imaging_engine 追加カバレッジ"""
import asyncio
from unittest.mock import MagicMock, patch

from src.core.imaging_engine import (
    ImagingEngine,
    ImagingJobParams,
    ImagingResult,
)


def _job(tmp_path, **overrides):
    d = {
        "job_id": "test-001",
        "evidence_id": "ev-001",
        "case_id": "case-001",
        "source_path": r"\\.\PhysicalDrive99",
        "output_dir": str(tmp_path / "out"),
        "verify_after_copy": False,
    }
    d.update(overrides)
    return ImagingJobParams(**d)


def test_disk_length_failure(tmp_path):
    async def _run():
        engine = ImagingEngine()
        with patch(
            "src.core.imaging_engine.open_device", return_value=42
        ), patch(
            "src.core.imaging_engine.get_disk_geometry",
            return_value={"bytes_per_sector": 512},
        ), patch(
            "src.core.imaging_engine.get_disk_length",
            side_effect=OSError("length fail"),
        ), patch(
            "src.core.imaging_engine.SafeDeviceHandle"
        ) as msdh:
            msdh.return_value.value = 42
            msdh.return_value.close = MagicMock()
            return await engine.execute(_job(tmp_path))

    r = asyncio.run(_run())
    assert r.status == "failed"
    assert r.error_code == "E2006"


def test_disk_space_insufficient(tmp_path):
    du = MagicMock()
    du.free = 1024

    async def _run():
        engine = ImagingEngine()
        with patch(
            "src.core.imaging_engine.open_device", return_value=42
        ), patch(
            "src.core.imaging_engine.get_disk_geometry",
            return_value={"bytes_per_sector": 512},
        ), patch(
            "src.core.imaging_engine.get_disk_length", return_value=100_000_000_000
        ), patch(
            "src.core.imaging_engine.verify_write_block", return_value=True
        ), patch(
            "src.core.imaging_engine.psutil.disk_usage", return_value=du
        ), patch(
            "src.core.imaging_engine.SafeDeviceHandle"
        ) as msdh:
            msdh.return_value.value = 42
            msdh.return_value.close = MagicMock()
            return await engine.execute(_job(tmp_path))

    r = asyncio.run(_run())
    assert r.status == "failed"
    assert r.error_code == "E1004"


def test_cancel_sets_event():
    async def _run():
        engine = ImagingEngine()
        await engine.cancel()
        return engine._cancel_event.is_set()

    assert asyncio.run(_run()) is True


def test_pause_resume():
    async def _run():
        engine = ImagingEngine()
        await engine.pause()
        assert not engine._pause_event.is_set()
        assert engine._progress["status"] == "paused"
        await engine.resume()
        assert engine._pause_event.is_set()
        assert engine._progress["status"] == "imaging"

    asyncio.run(_run())


def test_get_progress_default():
    engine = ImagingEngine()
    p = engine.get_progress()
    assert p.get("status") == "idle"


def test_set_progress_callback():
    engine = ImagingEngine()
    cb = MagicMock()
    engine.set_progress_callback(cb)
    assert engine._progress_callback is cb


def test_imaging_result_defaults():
    r = ImagingResult(job_id="test")
    assert r.status == "completed"
    assert r.copied_bytes == 0
    assert r.error_sectors == []
    assert r.incomplete_files == []


def test_imaging_job_params_defaults(tmp_path):
    p = ImagingJobParams(
        job_id="j1",
        evidence_id="e1",
        case_id="c1",
        source_path=r"\\.\PhysicalDrive1",
        output_dir=str(tmp_path / "o"),
    )
    assert p.buffer_size == 1_048_576
    assert p.hash_md5 is True
    assert p.hash_sha512 is False
