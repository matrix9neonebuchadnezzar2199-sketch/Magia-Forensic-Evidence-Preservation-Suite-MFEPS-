"""ImagingService 進捗・キャンセル API"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.imaging_service import ImagingService


def test_get_progress_from_engine():
    svc = ImagingService()
    eng = MagicMock()
    eng.get_progress.return_value = {"status": "imaging", "copied_bytes": 5}
    svc._engines["j"] = eng
    with patch("src.services.progress_broadcaster.get_broadcaster") as gb:
        gb.return_value.get_latest.return_value = None
        p = svc.get_progress("j")
        assert p["status"] == "imaging"


def test_get_progress_from_e01_writer():
    svc = ImagingService()
    w = MagicMock()
    w.get_progress.return_value = {
        "status": "imaging",
        "acquired_bytes": 100,
        "total_bytes": 1000,
        "percent": 10,
        "remaining": "completion in 0 minute(s) and 2 second(s)",
    }
    svc._e01_writers["je"] = w
    with patch("src.services.progress_broadcaster.get_broadcaster") as gb:
        gb.return_value.get_latest.return_value = None
        p = svc.get_progress("je")
        assert p["e01_percent"] == 10
        assert p["eta_seconds"] == 2.0


def test_get_progress_from_results():
    svc = ImagingService()
    svc._results["jr"] = {"status": "completed", "copied_bytes": 1}
    with patch("src.services.progress_broadcaster.get_broadcaster") as gb:
        gb.return_value.get_latest.return_value = None
        p = svc.get_progress("jr")
        assert p["status"] == "completed"


def test_cancel_imaging_e01_path():
    svc = ImagingService()
    w = MagicMock()
    w.cancel = AsyncMock()
    svc._e01_writers["jc"] = w

    async def _run():
        with patch.object(svc, "_update_job_status"):
            await svc.cancel_imaging("jc")

    asyncio.run(_run())
    w.cancel.assert_called_once()


def test_cancel_imaging_raw_engine():
    svc = ImagingService()
    eng = MagicMock()
    eng.cancel = AsyncMock()
    svc._engines["jr2"] = eng

    async def _run():
        with patch.object(svc, "_update_job_status"):
            await svc.cancel_imaging("jr2")

    asyncio.run(_run())
    eng.cancel.assert_called_once()


def test_pause_resume_imaging_service():
    svc = ImagingService()
    eng = MagicMock()
    eng.pause = AsyncMock()
    eng.resume = AsyncMock()
    svc._engines["jp"] = eng

    async def _run():
        await svc.pause_imaging("jp")
        await svc.resume_imaging("jp")

    asyncio.run(_run())
    eng.pause.assert_called_once()
    eng.resume.assert_called_once()
