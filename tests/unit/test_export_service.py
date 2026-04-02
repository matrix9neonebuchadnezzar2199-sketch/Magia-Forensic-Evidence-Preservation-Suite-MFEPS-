"""エクスポートサービスのテスト"""
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models.database import init_database, session_scope
from unittest.mock import patch

from src.models.schema import Case, ChainOfCustody, EvidenceItem, ImagingJob, HashRecord
from src.services.export_service import ExportService


@pytest.fixture
def db_with_job(tmp_path):
    init_database(tmp_path / "export.db")
    img_dir = tmp_path / "output"
    img_dir.mkdir()
    img_file = img_dir / "image.dd"
    img_file.write_bytes(b"\x00" * 1024)

    with session_scope() as s:
        c = Case(case_number="EXP-1", case_name="Export Test")
        s.add(c)
        s.flush()
        ev = EvidenceItem(case_id=c.id, evidence_number="EV-EXP-1")
        s.add(ev)
        s.flush()
        j = ImagingJob(
            evidence_id=ev.id,
            status="completed",
            output_path=str(img_file),
            output_format="raw",
            total_bytes=1024,
            copied_bytes=1024,
            completed_at=datetime.now(timezone.utc),
        )
        s.add(j)
        s.flush()
        hr = HashRecord(
            job_id=j.id,
            target="source",
            md5="abc123",
            sha256="def456",
        )
        s.add(hr)
        job_id = j.id
    return job_id, tmp_path


def test_export_creates_zip(db_with_job):
    job_id, _tmp = db_with_job
    svc = ExportService()
    path = svc.export_job(job_id, include_report=False)
    assert Path(path).exists()
    assert path.endswith(".zip")


def test_export_contains_image(db_with_job):
    job_id, _tmp = db_with_job
    svc = ExportService()
    path = svc.export_job(job_id, include_report=False)
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        assert any(n.startswith("image/") for n in names)


def test_export_contains_hash_log(db_with_job):
    job_id, _tmp = db_with_job
    svc = ExportService()
    path = svc.export_job(job_id, include_report=False)
    with zipfile.ZipFile(path) as zf:
        assert "hash_records.json" in zf.namelist()
        data = json.loads(zf.read("hash_records.json"))
        assert data[0]["md5"] == "abc123"


def test_export_contains_metadata(db_with_job):
    job_id, _tmp = db_with_job
    svc = ExportService()
    path = svc.export_job(job_id, include_report=False)
    with zipfile.ZipFile(path) as zf:
        assert "job_metadata.json" in zf.namelist()


def test_export_without_image(db_with_job):
    job_id, _tmp = db_with_job
    svc = ExportService()
    path = svc.export_job(job_id, include_image=False, include_report=False)
    with zipfile.ZipFile(path) as zf:
        assert not any(n.startswith("image/") for n in zf.namelist())


def test_export_nonexistent_job(db_with_job):
    _jid, _tmp = db_with_job
    svc = ExportService()
    with pytest.raises(ValueError, match="ジョブが見つかりません"):
        svc.export_job("nonexistent-id")


@pytest.fixture
def db_with_error_map(tmp_path):
    init_database(tmp_path / "export2.db")
    img_dir = tmp_path / "out2"
    img_dir.mkdir()
    img_file = img_dir / "x.dd"
    img_file.write_bytes(b"x")
    err_file = img_dir / "errors.json"
    err_file.write_text("{}")

    with session_scope() as s:
        c = Case(case_number="EXP-2", case_name="E2")
        s.add(c)
        s.flush()
        ev = EvidenceItem(case_id=c.id, evidence_number="EV-E2")
        s.add(ev)
        s.flush()
        j = ImagingJob(
            evidence_id=ev.id,
            status="completed",
            output_path=str(img_file),
            output_format="raw",
            error_map_path=str(err_file),
            completed_at=datetime.now(timezone.utc),
        )
        s.add(j)
        s.flush()
        s.add(
            ChainOfCustody(
                evidence_id=ev.id,
                action="created",
                actor_name="t",
                description="d",
            )
        )
        job_id = j.id
    return job_id


def test_export_includes_error_map_and_coc(db_with_error_map):
    job_id = db_with_error_map
    svc = ExportService()
    path = svc.export_job(job_id, include_report=False)
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        assert any(n.startswith("errors/") for n in names)
        assert "chain_of_custody.json" in names


def test_export_report_branch_mocked(db_with_job):
    job_id, tmp = db_with_job
    fake_html = tmp / "rep.html"
    fake_html.write_text("<html/>")
    with patch("src.services.export_service.ReportService") as RS:
        RS.return_value.generate_html.return_value = str(fake_html)
        path = ExportService().export_job(job_id, include_report=True)
    with zipfile.ZipFile(path) as zf:
        assert any(n.startswith("report/") for n in zf.namelist())


def test_export_report_generate_raises_still_writes_zip(db_with_job):
    job_id, _tmp = db_with_job
    with patch("src.services.export_service.ReportService") as RS:
        RS.return_value.generate_html.side_effect = RuntimeError("bad html")
        path = ExportService().export_job(job_id, include_report=True)
    assert Path(path).exists()
    with zipfile.ZipFile(path) as zf:
        assert "job_metadata.json" in zf.namelist()
