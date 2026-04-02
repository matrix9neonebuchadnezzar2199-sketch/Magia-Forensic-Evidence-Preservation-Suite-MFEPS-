"""Phase 3-5: OpticalService _run_imaging"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.optical_engine import OpticalAnalysisResult, OpticalImagingResult
from src.models.database import get_session, init_database
from src.models.schema import Case, EvidenceItem, ImagingJob
from src.services.optical_service import OpticalService


@pytest.fixture
def opt_db(tmp_path):
    init_database(tmp_path / "o.db")
    session = get_session()
    case = Case(case_number="OC", case_name="o")
    session.add(case)
    session.commit()
    ev = EvidenceItem(case_id=case.id, evidence_number="OE", media_type="dvd")
    session.add(ev)
    session.commit()
    job = ImagingJob(
        id="job-opt-1",
        evidence_id=ev.id,
        status="pending",
        source_path=r"\\.\D:",
        output_path=str(tmp_path / "o.iso"),
        output_format="iso",
    )
    session.add(job)
    session.commit()
    return {"job_id": job.id}


def _analysis():
    return OpticalAnalysisResult(
        capacity_bytes=1000,
        sector_count=1,
        sector_size=2048,
        capacity_source="t",
        media_type="DVD-Data",
    )


def test_optical_completed(opt_db, tmp_path):
    svc = OpticalService()
    jid = opt_db["job_id"]
    svc._progress[jid] = {
        "status": "pending",
        "copied_bytes": 0,
        "total_bytes": 1000,
        "speed_mibps": 0.0,
        "eta_seconds": 0,
        "error_count": 0,
        "current_file": r"\\.\D:",
    }
    eng = MagicMock()
    eng.image_optical = AsyncMock(
        return_value=OpticalImagingResult(
            status="completed",
            source_hashes={"md5": "a"},
            copied_bytes=1000,
            total_bytes=1000,
            elapsed_seconds=1.0,
            output_path=str(tmp_path / "o.iso"),
        )
    )
    svc._job_actors[jid] = "A"

    async def _run():
        await svc._run_imaging(
            jid,
            eng,
            r"\\.\D:",
            str(tmp_path / "o.iso"),
            _analysis(),
            False,
            False,
            lambda x: None,
            verify=False,
        )

    asyncio.run(_run())
    session = get_session()
    job = session.get(ImagingJob, opt_db["job_id"])
    assert job.status == "completed"


def test_optical_cancelled(opt_db, tmp_path):
    svc = OpticalService()
    jid = opt_db["job_id"]
    svc._progress[jid] = {
        "status": "pending",
        "copied_bytes": 0,
        "total_bytes": 1000,
        "speed_mibps": 0.0,
        "eta_seconds": 0,
        "error_count": 0,
        "current_file": r"\\.\D:",
    }
    eng = MagicMock()
    eng.image_optical = AsyncMock(side_effect=asyncio.CancelledError)

    async def _run():
        with pytest.raises(asyncio.CancelledError):
            await svc._run_imaging(
                jid,
                eng,
                r"\\.\D:",
                str(tmp_path / "o.iso"),
                _analysis(),
                False,
                False,
                lambda x: None,
            )

    asyncio.run(_run())
    session = get_session()
    job = session.get(ImagingJob, jid)
    assert job.status == "cancelled"


def test_optical_oserror(opt_db, tmp_path):
    svc = OpticalService()
    jid = opt_db["job_id"]
    svc._progress[jid] = {
        "status": "pending",
        "copied_bytes": 0,
        "total_bytes": 1000,
        "speed_mibps": 0.0,
        "eta_seconds": 0,
        "error_count": 0,
        "current_file": r"\\.\D:",
    }
    eng = MagicMock()
    eng.image_optical = AsyncMock(side_effect=OSError("x"))

    async def _run():
        await svc._run_imaging(
            jid,
            eng,
            r"\\.\D:",
            str(tmp_path / "o.iso"),
            _analysis(),
            False,
            False,
            lambda x: None,
        )

    asyncio.run(_run())
    session = get_session()
    job = session.get(ImagingJob, jid)
    assert job.status == "failed"


def test_optical_hash_mismatch_audit(opt_db, tmp_path):
    svc = OpticalService()
    jid = opt_db["job_id"]
    svc._progress[jid] = {
        "status": "pending",
        "copied_bytes": 0,
        "total_bytes": 1000,
        "speed_mibps": 0.0,
        "eta_seconds": 0,
        "error_count": 0,
        "current_file": r"\\.\D:",
    }
    eng = MagicMock()
    eng._cancel_event = MagicMock()
    eng.image_optical = AsyncMock(
        return_value=OpticalImagingResult(
            status="completed",
            source_hashes={"md5": "a"},
            copied_bytes=1000,
            total_bytes=1000,
            elapsed_seconds=1.0,
            output_path=str(tmp_path / "o.iso"),
        )
    )
    svc._job_actors[jid] = "A"

    p = tmp_path / "o.iso"
    p.write_bytes(b"zzz")

    async def _run():
        with patch(
            "src.services.optical_service.verify_image_hash",
            return_value={
                "computed": {"md5": "b"},
                "all_match": False,
                "cancelled": False,
            },
        ), patch("src.services.optical_service.get_audit_service") as ga:
            audit = MagicMock()
            ga.return_value = audit
            await svc._run_imaging(
                jid,
                eng,
                r"\\.\D:",
                str(p),
                _analysis(),
                False,
                False,
                lambda x: None,
                verify=True,
            )
            assert audit.add_entry.called

    asyncio.run(_run())
