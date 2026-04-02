"""Phase 3-5: E01 _run_e01_imaging"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.device_detector import DeviceInfo
from src.core.imaging_engine import ImagingJobParams
from src.models.database import get_session, init_database
from src.models.schema import Case, EvidenceItem, ImagingJob
from src.services.imaging_service import ImagingService


@pytest.fixture
def e01_db(tmp_path):
    init_database(tmp_path / "e01.db")
    session = get_session()
    case = Case(case_number="E01", case_name="e")
    session.add(case)
    session.commit()
    ev = EvidenceItem(case_id=case.id, evidence_number="EV", media_type="usb_hdd")
    session.add(ev)
    session.commit()
    job = ImagingJob(
        id="job-e01-1",
        evidence_id=ev.id,
        status="pending",
        source_path=r"\\.\P1",
        output_format="e01",
        output_path=str(tmp_path / "image.E01"),
    )
    session.add(job)
    session.commit()
    return {"job_id": job.id}


def _device():
    return DeviceInfo(
        device_path=r"\\.\P1",
        model="x",
        serial="s",
        capacity_bytes=1000,
        interface_type="USB",
        media_type="removable",
    )


def _params(jid, tmp_path):
    return ImagingJobParams(
        job_id=jid,
        evidence_id="1",
        case_id="1",
        source_path=r"\\.\P1",
        output_dir=str(tmp_path),
        output_format="e01",
    )


def test_e01_acquire_success(e01_db, tmp_path):
    svc = ImagingService()
    from src.core.e01_writer import E01Result

    mock_res = MagicMock(spec=E01Result)
    mock_res.success = True
    mock_res.md5 = "a"
    mock_res.sha256 = "b"
    mock_res.total_bytes = 100
    mock_res.acquired_bytes = 100
    mock_res.elapsed_seconds = 1.0
    mock_res.output_files = [str(tmp_path / "image.E01")]
    mock_res.error_code = None
    mock_res.error_message = None
    mock_res.incomplete_files = []
    mock_res.incomplete_total_bytes = 0
    mock_res.incomplete_file_records = []
    mock_res.ewfacquire_return_code = 0
    mock_res.command_line = "x"
    mock_res.ewfacquire_version = "1"
    mock_res.segment_count = 1
    mock_res.log_file_path = ""

    async def _run():
        with patch("src.core.e01_writer.E01Writer") as wcls:
            w = MagicMock()
            w.acquire = AsyncMock(return_value=mock_res)
            w.verify = AsyncMock(
                return_value=MagicMock(
                    skipped=True, skip_reason="n/a", verified=False
                )
            )
            w.info = AsyncMock(return_value=MagicMock(success=False))
            w.set_progress_callback = MagicMock()
            wcls.return_value = w
            await svc._run_e01_imaging(
                e01_db["job_id"],
                _params(e01_db["job_id"], tmp_path),
                _device(),
            )

    asyncio.run(_run())


def test_e01_acquire_failure_exit_code(e01_db, tmp_path):
    svc = ImagingService()
    from src.core.e01_writer import E01Result

    mock_res = MagicMock(spec=E01Result)
    mock_res.success = False
    mock_res.md5 = ""
    mock_res.sha256 = ""
    mock_res.total_bytes = 0
    mock_res.acquired_bytes = 0
    mock_res.elapsed_seconds = 0.0
    mock_res.output_files = []
    mock_res.error_code = "E7002"
    mock_res.error_message = "fail"
    mock_res.incomplete_files = []
    mock_res.incomplete_total_bytes = 0
    mock_res.incomplete_file_records = []

    async def _run():
        with patch("src.core.e01_writer.E01Writer") as wcls:
            w = MagicMock()
            w.acquire = AsyncMock(return_value=mock_res)
            w.set_progress_callback = MagicMock()
            wcls.return_value = w
            await svc._run_e01_imaging(
                e01_db["job_id"],
                _params(e01_db["job_id"], tmp_path),
                _device(),
            )

    asyncio.run(_run())


def test_e01_cancelled(e01_db, tmp_path):
    svc = ImagingService()

    async def _run():
        with patch("src.core.e01_writer.E01Writer") as wcls:
            w = MagicMock()
            w.acquire = AsyncMock(side_effect=asyncio.CancelledError)
            w.set_progress_callback = MagicMock()
            wcls.return_value = w
            with pytest.raises(asyncio.CancelledError):
                await svc._run_e01_imaging(
                    e01_db["job_id"],
                    _params(e01_db["job_id"], tmp_path),
                    _device(),
                )

    asyncio.run(_run())
