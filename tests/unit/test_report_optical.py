"""レポートの光学 / RFC3161 / コピーガード表示（Phase 5-4）"""
from unittest.mock import patch

import pytest

from src.models.database import get_session, init_database
from src.models.schema import Case, EvidenceItem, ImagingJob


@pytest.fixture
def optical_job_db(tmp_path):
    init_database(tmp_path / "rep_opt.db")
    session = get_session()
    case = Case(case_number="OP-1", case_name="Optical", examiner_name="T")
    session.add(case)
    session.commit()
    ev = EvidenceItem(case_id=case.id, evidence_number="EV-OP", media_type="dvd")
    session.add(ev)
    session.commit()
    job = ImagingJob(
        evidence_id=ev.id,
        status="completed",
        source_path=r"\\.\D:",
        total_bytes=1000,
        copied_bytes=1000,
        notes='{"capacity_source":"ioctl"}\n{"media_type":"DVD-Video","file_system":"UDF","sector_size":2048,"capacity_bytes":1000,"capacity_source":"ioctl","track_count":1}',
        copy_guard_type="css",
        copy_guard_detail='{"decrypt_method":"pydvdcss"}',
    )
    session.add(job)
    session.commit()
    jid = job.id
    return {"job_id": jid, "tmp_path": tmp_path}


class TestReportOpticalSections:
    @patch("src.services.report_service.get_imaging_service")
    def test_collect_includes_optical_and_rfc_fields(self, mock_gis, optical_job_db):
        from src.models.schema import HashRecord
        from src.services.report_service import ReportService

        session = get_session()
        hr = HashRecord(
            job_id=optical_job_db["job_id"],
            target="source",
            md5="x" * 32,
            sha256="a" * 64,
            rfc3161_token=b"\x01\x02",
            rfc3161_tsa_url="http://tsa.example",
        )
        session.add(hr)
        session.commit()

        mock_gis.return_value.get_e01_info.return_value = None
        svc = ReportService()
        data = svc._collect_report_data(optical_job_db["job_id"])
        assert data is not None
        assert data.get("optical_info") is not None
        assert data["optical_info"].get("media_type") == "DVD-Video"
        assert data.get("rfc3161", {}).get("has_timestamp") is True
        assert data.get("copy_guard_type") == "css"

    @patch("src.services.report_service.get_imaging_service")
    @patch("src.services.report_service.get_config")
    def test_html_contains_optical_section(
        self, mock_cfg, mock_gis, optical_job_db, tmp_path
    ):
        from src.models.schema import HashRecord
        from src.services.report_service import ReportService

        mock_cfg.return_value.reports_dir = tmp_path / "r"
        session = get_session()
        hr = HashRecord(
            job_id=optical_job_db["job_id"],
            target="source",
            sha256="a" * 64,
        )
        session.add(hr)
        session.commit()

        mock_gis.return_value.get_e01_info.return_value = None
        path = ReportService().generate_html(optical_job_db["job_id"])
        text = __import__("pathlib").Path(path).read_text(encoding="utf-8")
        assert "光学メディア情報" in text
        assert "DVD-Video" in text
