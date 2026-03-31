"""imaging_service の完了処理テスト"""
import asyncio

import pytest

from src.core.imaging_engine import ImagingResult
from src.models.database import get_session, init_database
from src.models.schema import Case, EvidenceItem, ImagingJob
from src.services.imaging_service import ImagingService


@pytest.fixture
def imaging_db(tmp_path):
    init_database(tmp_path / "imaging_test.db")
    session = get_session()

    case = Case(case_number="IMG-001", case_name="Imaging Test")
    session.add(case)
    session.commit()

    ev = EvidenceItem(
        case_id=case.id,
        evidence_number="EV-IMG",
        media_type="usb_hdd",
    )
    session.add(ev)
    session.commit()

    job = ImagingJob(
        id="test-job-001",
        evidence_id=ev.id,
        status="imaging",
        source_path=r"\\.\PhysicalDrive1",
        output_format="raw",
    )
    session.add(job)
    session.commit()

    return {"job_id": job.id}


class TestOnImagingComplete:
    def test_error_code_persisted_to_notes(self, imaging_db):
        svc = ImagingService()
        svc._job_actors["test-job-001"] = "Tester"

        result = ImagingResult(
            job_id="test-job-001",
            status="failed",
            source_hashes={"md5": "abc123"},
            total_bytes=1000,
            copied_bytes=500,
            error_code="E3007",
            error_message="予期せぬ EOF に到達しました",
        )

        asyncio.run(svc.on_imaging_complete(result))

        session = get_session()
        job = session.get(ImagingJob, "test-job-001")
        assert job is not None
        assert "[E3007]" in (job.notes or "")
        assert "予期せぬ EOF" in (job.notes or "")
        assert job.status == "failed"

    def test_success_no_error_notes(self, imaging_db):
        svc = ImagingService()
        svc._job_actors["test-job-001"] = "Tester"

        result = ImagingResult(
            job_id="test-job-001",
            status="completed",
            source_hashes={"md5": "d41d8cd98f00b204e9800998ecf8427e"},
            total_bytes=1000,
            copied_bytes=1000,
        )

        asyncio.run(svc.on_imaging_complete(result))

        session = get_session()
        job = session.get(ImagingJob, "test-job-001")
        assert job is not None
        assert job.status == "completed"
        assert "[E" not in (job.notes or "")
