"""カバレッジ 80% 達成用: imaging_service の未カバー分岐。"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from src.core.imaging_engine import ImagingResult
from src.models.database import get_session, init_database
from src.models.schema import Case, EvidenceItem, ImagingJob
from src.services.imaging_service import ImagingService


@pytest.fixture
def svc_with_db(tmp_path):
    init_database(tmp_path / "cov80.db")
    session = get_session()
    case = Case(case_number="COV80", case_name="Coverage Test")
    session.add(case)
    session.commit()
    ev = EvidenceItem(
        case_id=case.id, evidence_number="EV80", media_type="usb_hdd"
    )
    session.add(ev)
    session.commit()
    job = ImagingJob(
        id="cov80-job",
        evidence_id=ev.id,
        status="pending",
        source_path=r"\\.\PhysicalDrive99",
        output_path=str(tmp_path / "image.dd"),
        output_format="raw",
    )
    session.add(job)
    session.commit()
    svc = ImagingService()
    return svc, job.id, ev.id, tmp_path


def test_on_imaging_complete_with_incomplete_files(svc_with_db):
    svc, job_id, _ev_id, _tmp = svc_with_db
    svc._job_actors[job_id] = "Tester"
    result = ImagingResult(
        job_id=job_id,
        status="cancelled",
        source_hashes={"md5": "abc"},
        total_bytes=1000,
        copied_bytes=500,
        incomplete_file_records=[
            {"path": "image_001.dd", "size": 500, "expected": 1000}
        ],
    )

    with patch("src.services.progress_broadcaster.get_broadcaster") as gb:
        gb.return_value.clear_job = MagicMock()
        asyncio.run(svc.on_imaging_complete(result))

    session = get_session()
    job = session.get(ImagingJob, job_id)
    notes = job.notes or ""
    assert "incomplete" in notes.lower() or "image_001" in notes


def test_on_imaging_complete_error_code_only(svc_with_db):
    svc, job_id, _ev_id, _tmp = svc_with_db
    svc._job_actors[job_id] = "Tester"
    result = ImagingResult(
        job_id=job_id,
        status="failed",
        source_hashes={},
        total_bytes=100,
        copied_bytes=0,
        error_code="E3001",
        error_message=None,
    )
    with patch("src.services.progress_broadcaster.get_broadcaster") as gb:
        gb.return_value.clear_job = MagicMock()
        asyncio.run(svc.on_imaging_complete(result))
    session = get_session()
    job = session.get(ImagingJob, job_id)
    assert "[E3001]" in (job.notes or "")


def test_on_imaging_complete_error_message_only(svc_with_db):
    svc, job_id, _ev_id, _tmp = svc_with_db
    svc._job_actors[job_id] = "Tester"
    result = ImagingResult(
        job_id=job_id,
        status="failed",
        source_hashes={},
        total_bytes=100,
        copied_bytes=0,
        error_code=None,
        error_message="Device not found",
    )
    with patch("src.services.progress_broadcaster.get_broadcaster") as gb:
        gb.return_value.clear_job = MagicMock()
        asyncio.run(svc.on_imaging_complete(result))
    session = get_session()
    job = session.get(ImagingJob, job_id)
    assert "Device not found" in (job.notes or "")


def test_get_e01_info_from_db_notes(svc_with_db):
    svc, job_id, _ev_id, _tmp = svc_with_db
    ewfinfo_payload = json.dumps(
        {
            "type": "ewfinfo",
            "sections": {"Media information": {"Bytes per sector": "512"}},
            "raw_excerpt": (
                "ewfinfo 20230405\nMedia information\n\tBytes per sector: 512"
            ),
        }
    )
    session = get_session()
    job = session.get(ImagingJob, job_id)
    job.notes = f"some earlier notes\n{ewfinfo_payload}"
    session.commit()

    info = svc.get_e01_info(job_id)
    assert info is not None
    assert info.success is True
    assert "Media information" in info.sections


def test_get_e01_info_returns_none_for_no_notes(svc_with_db):
    svc, job_id, _ev_id, _tmp = svc_with_db
    session = get_session()
    job = session.get(ImagingJob, job_id)
    job.notes = ""
    session.commit()

    assert svc.get_e01_info(job_id) is None


def test_get_progress_e01_zero_speed(svc_with_db):
    svc, _job_id, _ev_id, _tmp = svc_with_db
    w = MagicMock()
    w.get_progress.return_value = {
        "status": "imaging",
        "acquired_bytes": 50,
        "total_bytes": 100,
        "percent": 50,
        "speed_bytes": 0,
        "remaining": "",
    }
    svc._e01_writers["speed-test"] = w
    with patch("src.services.progress_broadcaster.get_broadcaster") as gb:
        gb.return_value.get_latest.return_value = None
        p = svc.get_progress("speed-test")
        assert p["speed_mibps"] == 0.0
        assert p["copied_bytes"] == 50
