"""dashboard_service カバレッジ"""
from datetime import datetime, timezone

import pytest

from src.models.database import init_database, session_scope
from src.models.schema import Case, EvidenceItem, ImagingJob
from src.services.dashboard_service import get_dashboard_counts, get_recent_jobs


@pytest.fixture
def db(tmp_path):
    init_database(tmp_path / "dash_cov.db")
    with session_scope() as s:
        c = Case(case_number="DASH-1", case_name="Dashboard")
        s.add(c)
        s.flush()
        ev = EvidenceItem(case_id=c.id, evidence_number="EV-D1", media_type="usb_hdd")
        s.add(ev)
        s.flush()
        j = ImagingJob(
            evidence_id=ev.id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
            elapsed_seconds=120,
            avg_speed_mbps=45.0,
            error_count=2,
        )
        s.add(j)


def test_counts(db):
    c = get_dashboard_counts()
    assert c["cases"] == 1
    assert c["evidence"] == 1
    assert c["images"] == 1
    assert c["errors"] == 2


def test_recent_jobs(db):
    jobs = get_recent_jobs(10)
    assert len(jobs) == 1
    assert jobs[0]["status"] == "completed"
    assert "2:" in jobs[0]["duration"]


def test_empty_db(tmp_path):
    init_database(tmp_path / "dash_empty.db")
    c = get_dashboard_counts()
    assert c["cases"] == 0
    assert get_recent_jobs() == []


def test_recent_jobs_limit(tmp_path):
    init_database(tmp_path / "dash_limit.db")
    with session_scope() as s:
        c = Case(case_number="LIM-1", case_name="Limit")
        s.add(c)
        s.flush()
        ev = EvidenceItem(case_id=c.id, evidence_number="EV-L1")
        s.add(ev)
        s.flush()
        for _i in range(20):
            s.add(
                ImagingJob(
                    evidence_id=ev.id,
                    status="completed",
                    completed_at=datetime.now(timezone.utc),
                )
            )
    jobs = get_recent_jobs(5)
    assert len(jobs) == 5
