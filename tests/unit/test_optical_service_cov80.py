"""カバレッジ 80% 達成用: optical_service の未カバー分岐。"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.copy_guard_analyzer import CopyGuardResult
from src.core.optical_engine import OpticalAnalysisResult, OpticalImagingResult
from src.models.database import get_session, init_database
from src.models.schema import Case, ChainOfCustody, EvidenceItem, ImagingJob
from src.services.optical_service import OpticalService
from src.utils.audit_categories import AuditCategories


def _analysis():
    return OpticalAnalysisResult(
        capacity_bytes=2000,
        sector_count=1,
        sector_size=2048,
        capacity_source="toc",
        media_type="DVD-Data",
    )


@pytest.fixture
def opt_svc_db(tmp_path):
    init_database(tmp_path / "optcov.db")
    session = get_session()
    case = Case(case_number="OPT-COV", case_name="Optical Coverage")
    session.add(case)
    session.commit()
    ev = EvidenceItem(
        case_id=case.id, evidence_number="OPTEV", media_type="dvd"
    )
    session.add(ev)
    session.commit()
    job = ImagingJob(
        id="optcov-job",
        evidence_id=ev.id,
        status="pending",
        source_path=r"\\.\CdRom0",
        output_path=str(tmp_path / "opt.iso"),
        output_format="iso",
    )
    session.add(job)
    session.commit()
    svc = OpticalService()
    svc._progress[job.id] = {
        "status": "pending",
        "copied_bytes": 0,
        "total_bytes": 2000,
        "speed_mibps": 0.0,
        "eta_seconds": 0,
        "error_count": 0,
        "current_file": r"\\.\CdRom0",
    }
    return svc, job.id, ev.id, tmp_path


def test_optical_verify_exception_falls_back_to_pending(opt_svc_db):
    svc, jid, _ev_id, tmp_path = opt_svc_db
    eng = MagicMock()
    eng._cancel_event = MagicMock()
    eng.image_optical = AsyncMock(
        return_value=OpticalImagingResult(
            status="completed",
            source_hashes={"md5": "abc123", "sha256": "def456"},
            copied_bytes=2000,
            total_bytes=2000,
            elapsed_seconds=2.0,
            output_path=str(tmp_path / "opt.iso"),
        )
    )
    svc._job_actors[jid] = "Tester"
    (tmp_path / "opt.iso").write_bytes(b"\x00" * 2000)

    async def _run():
        with patch(
            "src.services.optical_service.verify_image_hash",
            side_effect=RuntimeError("verify crashed"),
        ), patch("src.services.optical_service.get_audit_service") as ga, patch(
            "src.core.copy_guard_analyzer.CopyGuardAnalyzer"
        ) as MockCGA:
            MockCGA.return_value.analyze.return_value = CopyGuardResult()
            audit = MagicMock()
            ga.return_value = audit
            await svc._run_imaging(
                jid,
                eng,
                r"\\.\CdRom0",
                str(tmp_path / "opt.iso"),
                _analysis(),
                False,
                False,
                lambda x: None,
                verify=True,
            )
            assert any(
                c.kwargs.get("level") == "WARN"
                for c in audit.add_entry.call_args_list
                if c.kwargs
            )

    asyncio.run(_run())
    assert svc._progress[jid]["match_result"] == "pending"


def test_optical_decrypt_method_creates_coc_and_audit(opt_svc_db):
    svc, jid, ev_id, tmp_path = opt_svc_db
    eng = MagicMock()
    eng.image_optical = AsyncMock(
        return_value=OpticalImagingResult(
            status="completed",
            source_hashes={"md5": "x"},
            copied_bytes=2000,
            total_bytes=2000,
            elapsed_seconds=1.0,
            output_path=str(tmp_path / "opt.iso"),
            decrypt_method="pydvdcss",
            css_scrambled=True,
        )
    )
    svc._job_actors[jid] = "Tester"

    async def _run():
        with patch("src.services.optical_service.get_audit_service") as ga, patch(
            "src.core.copy_guard_analyzer.CopyGuardAnalyzer"
        ) as MockCGA:
            MockCGA.return_value.analyze.return_value = CopyGuardResult()
            audit = MagicMock()
            ga.return_value = audit
            await svc._run_imaging(
                jid,
                eng,
                r"\\.\CdRom0",
                str(tmp_path / "opt.iso"),
                _analysis(),
                True,
                False,
                lambda x: None,
                verify=False,
            )
            assert any(
                c.kwargs.get("category") == AuditCategories.DECRYPT_USED
                for c in audit.add_entry.call_args_list
                if c.kwargs
            )

    asyncio.run(_run())

    session = get_session()
    job = session.get(ImagingJob, jid)
    assert job.copy_guard_detail
    detail = json.loads(job.copy_guard_detail)
    assert detail["decrypt_method"] == "pydvdcss"
    assert detail["css_scrambled_media"] is True

    coc = (
        session.query(ChainOfCustody)
        .filter_by(evidence_id=ev_id)
        .first()
    )
    assert coc is not None
    assert "復号" in coc.description or "pydvdcss" in coc.description


def test_optical_copy_guard_failure_continues(opt_svc_db):
    svc, jid, _ev_id, tmp_path = opt_svc_db
    eng = MagicMock()
    eng.image_optical = AsyncMock(
        return_value=OpticalImagingResult(
            status="completed",
            source_hashes={"md5": "z"},
            copied_bytes=2000,
            total_bytes=2000,
            elapsed_seconds=0.5,
            output_path=str(tmp_path / "opt.iso"),
        )
    )
    svc._job_actors[jid] = "Tester"

    async def _run():
        with patch(
            "src.core.copy_guard_analyzer.CopyGuardAnalyzer"
        ) as MockCGA:
            MockCGA.return_value.analyze.side_effect = RuntimeError("CGA crash")
            await svc._run_imaging(
                jid,
                eng,
                r"\\.\CdRom0",
                str(tmp_path / "opt.iso"),
                _analysis(),
                False,
                False,
                lambda x: None,
                verify=False,
            )

    asyncio.run(_run())
    session = get_session()
    job = session.get(ImagingJob, jid)
    assert job.status == "completed"


def test_optical_no_verify_sets_pending(opt_svc_db):
    svc, jid, _ev_id, tmp_path = opt_svc_db
    eng = MagicMock()
    eng.image_optical = AsyncMock(
        return_value=OpticalImagingResult(
            status="completed",
            source_hashes={"md5": "abc"},
            copied_bytes=2000,
            total_bytes=2000,
            elapsed_seconds=1.0,
            output_path=str(tmp_path / "opt.iso"),
        )
    )
    svc._job_actors[jid] = "Tester"

    async def _run():
        await svc._run_imaging(
            jid,
            eng,
            r"\\.\CdRom0",
            str(tmp_path / "opt.iso"),
            _analysis(),
            False,
            False,
            lambda x: None,
            verify=False,
        )

    asyncio.run(_run())
    progress = svc._progress[jid]
    assert progress["match_result"] == "pending"
    assert progress["verify_hashes"] == {}
