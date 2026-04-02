"""OpticalService の軽量 API テスト"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.optical_service import OpticalService


def test_get_progress_merges_broadcaster():
    svc = OpticalService()
    svc._progress["j1"] = {"status": "imaging", "copied_bytes": 1}
    with patch("src.services.progress_broadcaster.get_broadcaster") as gb:
        gb.return_value.get_latest.return_value = {
            "job_id": "j1",
            "copied_bytes": 99,
        }
        d = svc.get_progress("j1")
        assert d["copied_bytes"] == 99


def test_get_progress_unknown_job():
    svc = OpticalService()
    with patch("src.services.progress_broadcaster.get_broadcaster") as gb:
        gb.return_value.get_latest.return_value = None
        d = svc.get_progress("missing")
        assert d.get("status") == "unknown"


def test_cancel_imaging_calls_engine():
    svc = OpticalService()
    eng = MagicMock()
    eng.cancel = AsyncMock()
    svc._engines["jid"] = eng
    asyncio.run(svc.cancel_imaging("jid"))
    eng.cancel.assert_called_once()


def test_pause_resume_imaging():
    svc = OpticalService()
    eng = MagicMock()
    eng.pause = AsyncMock()
    eng.resume = AsyncMock()
    svc._engines["p"] = eng
    asyncio.run(svc.pause_imaging("p"))
    asyncio.run(svc.resume_imaging("p"))
    eng.pause.assert_called_once()
    eng.resume.assert_called_once()
