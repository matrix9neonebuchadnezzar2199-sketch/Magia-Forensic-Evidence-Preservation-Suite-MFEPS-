"""Phase 10: カバレッジ 80% ゲート向けの補完テスト"""
from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.core.imaging_engine import ImagingResult
from src.models.database import init_database, session_scope
from src.models.schema import Case, EvidenceItem, ImagingJob
from src.services.export_service import ExportService
from src.services.imaging_service import _merge_e01_verify_hashes_from_source
from src.services.remote_service import RemoteService
from src.utils.config import reload_config


class TestMergeE01Verify:
    def test_returns_none_if_verify_empty(self):
        r = ImagingResult(
            job_id="j",
            verify_hashes={},
            source_hashes={"md5": "a"},
            match_result="matched",
        )
        assert _merge_e01_verify_hashes_from_source(None, r) is None

    def test_e01_merges_md5_from_source(self):
        job = MagicMock()
        job.output_format = "e01"
        r = ImagingResult(
            job_id="j",
            verify_hashes={"md5": "", "sha256": "sx"},
            source_hashes={"md5": "sm", "sha256": "sx"},
            match_result="matched",
        )
        m = _merge_e01_verify_hashes_from_source(job, r)
        assert m is not None
        assert m["md5"] == "sm"

    def test_non_e01_returns_verify_copy(self):
        job = MagicMock()
        job.output_format = "raw"
        r = ImagingResult(
            job_id="j",
            verify_hashes={"sha256": "v"},
            source_hashes={"sha256": "s"},
            match_result="matched",
        )
        m = _merge_e01_verify_hashes_from_source(job, r)
        assert m == {"sha256": "v"}

    def test_mismatch_skips_merge_behavior(self):
        job = MagicMock()
        job.output_format = "e01"
        r = ImagingResult(
            job_id="j",
            verify_hashes={"md5": "x"},
            source_hashes={"md5": "y"},
            match_result="mismatched",
        )
        m = _merge_e01_verify_hashes_from_source(job, r)
        assert m == {"md5": "x"}


class TestRemoteServiceExhaustive:
    def test_all_methods(self):
        s = RemoteService()
        assert s.register_agent("a", "h", "1.1.1.1", {"k": "v"})
        assert len(s.get_agents()) == 1
        assert s.get_agent("a") is not None
        jid = s.start_remote_imaging("a", r"\\.\X", "c", "e")
        assert s.update_progress(jid, {"status": "imaging", "pct": 50})
        assert s.complete_job(jid, {"status": "completed", "path": "/x"})
        st = s.get_job_status(jid)
        assert st["status"] == "completed"
        assert len(s.get_all_jobs()) == 1
        assert s.cancel_remote_imaging("missing") is False
        jid2 = s.start_remote_imaging("a", r"\\.\Y", "c", "e2")
        assert s.cancel_remote_imaging(jid2)
        assert s.unregister_agent("a")
        assert s.get_agent("a") is None
        assert s.heartbeat("nope") is False


def test_export_e01_segment_files_in_zip(monkeypatch, tmp_path):
    """E01 時に同一ディレクトリの .E* セグメントを zip に含める分岐"""
    monkeypatch.setenv("MFEPS_OUTPUT_DIR", str(tmp_path / "output_root"))
    reload_config()

    init_database(tmp_path / "e01exp.db")
    case_dir = tmp_path / "output_root" / "CASE" / "EV"
    case_dir.mkdir(parents=True)
    seg = case_dir / "image.E01"
    seg.write_bytes(b"x")
    (case_dir / "image.E02").write_bytes(b"y")

    with session_scope() as session:
        case = Case(case_number="CASE", case_name="c")
        session.add(case)
        session.flush()
        ev = EvidenceItem(case_id=case.id, evidence_number="EV", media_type="usb_hdd")
        session.add(ev)
        session.flush()
        job = ImagingJob(
            id="11111111-1111-4111-8111-111111111111",
            evidence_id=ev.id,
            status="completed",
            source_path="s",
            output_path=str(seg),
            output_format="e01",
            total_bytes=2,
            completed_at=datetime.now(timezone.utc),
        )
        session.add(job)

    path = ExportService().export_job(
        "11111111-1111-4111-8111-111111111111", include_report=False
    )
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        assert any("image.E01" in n for n in names)
        assert any("image.E02" in n for n in names)
