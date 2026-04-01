"""dashboard_service 集計テスト"""
import pytest

from src.models.database import init_database, session_scope
from src.models.schema import Case, EvidenceItem, ImagingJob
from src.services.dashboard_service import get_dashboard_counts, get_recent_jobs


@pytest.fixture
def dash_db(tmp_path, monkeypatch):
    dbp = tmp_path / "dash.db"
    init_database(dbp)
    with session_scope() as session:
        c = Case(case_number="D-001", case_name="Dash")
        session.add(c)
        session.flush()
        ev = EvidenceItem(
            case_id=c.id,
            evidence_number="EV-D",
            media_type="usb_hdd",
        )
        session.add(ev)
        session.flush()
        job = ImagingJob(
            evidence_id=ev.id,
            status="completed",
            source_path=r"\\.\X",
            output_path=str(tmp_path / "out.dd"),
            output_format="raw",
            error_count=3,
        )
        session.add(job)
    yield


def test_get_dashboard_counts(dash_db):
    c = get_dashboard_counts()
    assert c["cases"] == 1
    assert c["evidence"] == 1
    assert c["images"] == 1
    assert c["errors"] == 3


def test_get_recent_jobs(dash_db):
    rows = get_recent_jobs(5)
    assert len(rows) == 1
    assert rows[0]["case"] == "D-001"
    assert rows[0]["evidence"] == "EV-D"
    assert rows[0]["status"] == "completed"
