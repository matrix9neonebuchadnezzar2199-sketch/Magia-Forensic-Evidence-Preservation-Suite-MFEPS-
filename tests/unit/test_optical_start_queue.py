"""OpticalService.start_optical_imaging のキュー投入までを結合テスト"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.job_queue import JobPriority
from src.core.optical_engine import OpticalAnalysisResult
from src.models.database import init_database
from src.services.optical_service import OpticalService
from src.utils.config import reload_config


@pytest.mark.asyncio
async def test_start_optical_imaging_submits_to_queue(monkeypatch, tmp_path):
    monkeypatch.setenv("MFEPS_OUTPUT_DIR", str(tmp_path / "oo"))
    reload_config()
    init_database(tmp_path / "optq.db")

    analysis = OpticalAnalysisResult(
        drive_path=r"\\.\CdRom0",
        media_type="DVD-Data",
        capacity_bytes=4096,
    )
    wb = {
        "hardware_blocked": False,
        "registry_blocked": False,
        "is_protected": False,
    }

    mock_q = MagicMock()

    async def submit(job_id, coro_factory, priority):
        assert priority == JobPriority.NORMAL
        await coro_factory()
        return job_id, asyncio.create_task(asyncio.sleep(0))

    mock_q.submit = submit

    with patch(
        "src.core.job_queue.get_job_queue", return_value=mock_q
    ), patch(
        "src.services.optical_service.check_write_protection", return_value=wb
    ), patch.object(
        OpticalService, "_run_imaging", new_callable=AsyncMock
    ) as rim:
        svc = OpticalService()
        jid = await svc.start_optical_imaging(
            r"\\.\CdRom0",
            "CASE-Q",
            "EV-Q",
            analysis,
        )
        assert len(jid) == 36
        assert jid in svc._tasks
        rim.assert_called_once()


@pytest.mark.asyncio
async def test_start_optical_imaging_raw_extension(monkeypatch, tmp_path):
    """output_format が ISO 以外のとき .dd 拡張子分岐"""
    monkeypatch.setenv("MFEPS_OUTPUT_DIR", str(tmp_path / "oo2"))
    reload_config()
    init_database(tmp_path / "optq2.db")

    analysis = OpticalAnalysisResult(
        drive_path=r"\\.\CdRom1",
        media_type="CD-ROM",
        capacity_bytes=2048,
    )
    wb = {
        "hardware_blocked": False,
        "registry_blocked": False,
        "is_protected": False,
    }
    mock_q = MagicMock()

    async def submit(job_id, coro_factory, priority):
        await coro_factory()
        return job_id, asyncio.create_task(asyncio.sleep(0))

    mock_q.submit = submit

    with patch("src.core.job_queue.get_job_queue", return_value=mock_q), patch(
        "src.services.optical_service.check_write_protection", return_value=wb
    ), patch.object(OpticalService, "_run_imaging", new_callable=AsyncMock):
        svc = OpticalService()
        jid = await svc.start_optical_imaging(
            r"\\.\CdRom1",
            "CASE-R",
            "EV-R",
            analysis,
            output_format="RAW",
        )
        assert len(jid) == 36
