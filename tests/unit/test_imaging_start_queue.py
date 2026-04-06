"""ImagingService.start_imaging（RAW）のキュー投入まで"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.device_detector import DeviceInfo
from src.core.job_queue import JobPriority
from src.models.database import init_database
from src.services.imaging_service import ImagingService
from src.utils.config import reload_config


@pytest.mark.asyncio
async def test_start_imaging_raw_submits_to_queue(monkeypatch, tmp_path):
    monkeypatch.setenv("MFEPS_OUTPUT_DIR", str(tmp_path / "im"))
    reload_config()
    init_database(tmp_path / "imraw.db")

    dev = DeviceInfo(
        device_path=r"\\.\PhysicalDrive99",
        model="T",
        serial="S",
        capacity_bytes=10_000,
        interface_type="USB",
        media_type="USB",
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

    with patch("src.core.job_queue.get_job_queue", return_value=mock_q), patch(
        "src.services.imaging_service.check_write_protection", return_value=wb
    ), patch(
        "src.services.imaging_service.get_general_storage", return_value={}
    ), patch(
        "src.services.imaging_service.get_current_role", return_value="admin"
    ), patch.object(ImagingService, "_run_imaging", new_callable=AsyncMock) as rim:
        svc = ImagingService()
        jid = await svc.start_imaging(
            dev,
            "CASE-ISQ",
            "EV-ISQ",
            output_format="raw",
            progress_callback=lambda _p: None,
        )
        assert len(jid) == 36
        rim.assert_called_once()
