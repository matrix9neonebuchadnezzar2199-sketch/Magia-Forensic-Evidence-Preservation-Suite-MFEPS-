"""Phase 3-5: ImagingService _run_imaging exception handling"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.imaging_engine import ImagingJobParams, ImagingResult
from src.models.database import get_session, init_database
from src.models.schema import Case, EvidenceItem, ImagingJob
from src.services.imaging_service import ImagingService


@pytest.fixture
def svc_db(tmp_path):
    init_database(tmp_path / "t.db")
    session = get_session()
    case = Case(case_number="C-3", case_name="t")
    session.add(case)
    session.commit()
    ev = EvidenceItem(case_id=case.id, evidence_number="E3", media_type="usb_hdd")
    session.add(ev)
    session.commit()
    job = ImagingJob(
        id="job-svc-1",
        evidence_id=ev.id,
        status="pending",
        source_path=r"\\.\X",
        output_format="raw",
    )
    session.add(job)
    session.commit()
    return {"job_id": job.id, "evidence_id": ev.id}


def test_run_imaging_completed_updates_db(svc_db):
    svc = ImagingService()
    params = ImagingJobParams(
        job_id=svc_db["job_id"],
        evidence_id=str(svc_db["evidence_id"]),
        case_id="c",
        source_path=r"\\.\X",
        output_dir="/tmp",
        verify_after_copy=False,
    )
    eng = MagicMock()
    eng.execute = AsyncMock(
        return_value=ImagingResult(
            job_id=svc_db["job_id"],
            status="completed",
            source_hashes={"md5": "a"},
            total_bytes=1,
            copied_bytes=1,
        )
    )
    svc._job_actors[svc_db["job_id"]] = "Actor"

    async def _run():
        await svc._run_imaging(svc_db["job_id"], eng, params)

    asyncio.run(_run())
    session = get_session()
    job = session.get(ImagingJob, svc_db["job_id"])
    assert job.status == "completed"


def test_run_imaging_cancelled(svc_db):
    svc = ImagingService()
    params = ImagingJobParams(
        job_id=svc_db["job_id"],
        evidence_id=str(svc_db["evidence_id"]),
        case_id="c",
        source_path=r"\\.\X",
        output_dir="/tmp",
    )
    eng = MagicMock()
    eng.execute = AsyncMock(side_effect=asyncio.CancelledError)

    async def _run():
        with pytest.raises(asyncio.CancelledError):
            await svc._run_imaging(svc_db["job_id"], eng, params)

    asyncio.run(_run())
    session = get_session()
    job = session.get(ImagingJob, svc_db["job_id"])
    assert job.status == "cancelled"


def test_run_imaging_oserror(svc_db):
    svc = ImagingService()
    params = ImagingJobParams(
        job_id=svc_db["job_id"],
        evidence_id=str(svc_db["evidence_id"]),
        case_id="c",
        source_path=r"\\.\X",
        output_dir="/tmp",
    )
    eng = MagicMock()
    eng.execute = AsyncMock(side_effect=OSError("io"))

    async def _run():
        await svc._run_imaging(svc_db["job_id"], eng, params)

    asyncio.run(_run())
    assert svc._results[svc_db["job_id"]]["status"] == "failed"
