"""ORM スキーマのテスト"""

import pytest

from src.models.database import init_database, get_session
from src.models.schema import (
    Case,
    EvidenceItem,
    ImagingJob,
    AppSettings,
)


@pytest.fixture
def db_session(tmp_path):
    init_database(tmp_path / "test_schema.db")
    return get_session()


class TestSchemaCreation:
    def test_create_case(self, db_session):
        case = Case(case_number="TEST-001", case_name="Test Case")
        db_session.add(case)
        db_session.commit()
        fetched = db_session.query(Case).filter_by(case_number="TEST-001").first()
        assert fetched is not None
        assert fetched.status == "active"

    def test_create_evidence_with_case(self, db_session):
        case = Case(case_number="TEST-002", case_name="Evidence Test")
        db_session.add(case)
        db_session.commit()

        ev = EvidenceItem(
            case_id=case.id,
            evidence_number="EV-001",
            media_type="usb_hdd",
        )
        db_session.add(ev)
        db_session.commit()
        assert ev.id is not None

    def test_imaging_job_write_block_method_default(self, db_session):
        case = Case(case_number="TEST-003", case_name="WB Test")
        db_session.add(case)
        db_session.commit()
        ev = EvidenceItem(case_id=case.id, evidence_number="EV-WB", media_type="usb_hdd")
        db_session.add(ev)
        db_session.commit()

        job = ImagingJob(evidence_id=ev.id, source_path=r"\\.\PhysicalDrive1")
        db_session.add(job)
        db_session.commit()
        assert job.write_block_method == "none"

    def test_app_settings_singleton(self, db_session):
        settings = AppSettings(
            id=1,
            legal_consent_accepted=True,
            legal_consent_version="1.0",
        )
        db_session.add(settings)
        db_session.commit()
        fetched = db_session.get(AppSettings, 1)
        assert fetched.legal_consent_accepted is True

    def test_cascade_delete(self, db_session):
        case = Case(case_number="TEST-DEL", case_name="Cascade")
        db_session.add(case)
        db_session.commit()
        ev = EvidenceItem(case_id=case.id, evidence_number="EV-DEL", media_type="usb_hdd")
        db_session.add(ev)
        db_session.commit()

        db_session.delete(case)
        db_session.commit()
        assert (
            db_session.query(EvidenceItem).filter_by(evidence_number="EV-DEL").first()
            is None
        )
