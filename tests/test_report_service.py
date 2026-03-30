"""レポートサービスのテスト"""

import pytest
from unittest.mock import patch, MagicMock

from src.models.database import init_database, get_session
from src.models.schema import Case, EvidenceItem, ImagingJob, HashRecord


@pytest.fixture
def populated_db(tmp_path):
    init_database(tmp_path / "report_test.db")
    session = get_session()
    case = Case(
        case_number="RPT-001", case_name="Report Test", examiner_name="Tester"
    )
    session.add(case)
    session.commit()
    ev = EvidenceItem(case_id=case.id, evidence_number="EV-RPT", media_type="usb_hdd")
    session.add(ev)
    session.commit()
    job = ImagingJob(
        evidence_id=ev.id,
        status="completed",
        source_path=r"\\.\PhysicalDrive1",
        total_bytes=1_000_000,
        copied_bytes=1_000_000,
        elapsed_seconds=10.5,
        avg_speed_mbps=95.2,
        error_count=0,
        write_block_method="software",
    )
    session.add(job)
    session.commit()
    src_hash = HashRecord(
        job_id=job.id,
        target="source",
        md5="d41d8cd98f00b204e9800998ecf8427e",
        sha1="da39a3ee5e6b4b0d3255bfef95601890afd80709",
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    ver_hash = HashRecord(
        job_id=job.id,
        target="verify",
        md5="d41d8cd98f00b204e9800998ecf8427e",
        sha1="da39a3ee5e6b4b0d3255bfef95601890afd80709",
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        match_result="matched",
    )
    session.add_all([src_hash, ver_hash])
    session.commit()
    return {"job_id": job.id, "tmp_path": tmp_path}


class TestReportDataCollection:
    def test_collect_report_data(self, populated_db):
        from src.services.report_service import ReportService

        svc = ReportService()
        data = svc._collect_report_data(populated_db["job_id"])
        assert data is not None
        assert data["case_number"] == "RPT-001"
        assert data["match_result"] == "matched"
        assert data["write_block_method"] == "software"

    def test_collect_nonexistent_job(self, populated_db):
        from src.services.report_service import ReportService

        svc = ReportService()
        data = svc._collect_report_data("nonexistent-id")
        assert data is None


class TestHTMLReport:
    @patch("src.services.report_service.get_config")
    def test_generate_html(self, mock_get_config, populated_db):
        from src.services.report_service import ReportService

        reports_dir = populated_db["tmp_path"] / "reports"
        mock_cfg = MagicMock()
        mock_cfg.reports_dir = reports_dir
        mock_get_config.return_value = mock_cfg

        svc = ReportService()
        path = svc.generate_html(populated_db["job_id"])
        assert path.endswith(".html")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "RPT-001" in content
        assert "書き込み保護" in content
        assert "ソフトウェアのみ" in content
