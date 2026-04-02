"""stats_service ユニットテスト"""
import pytest
from datetime import datetime, timezone

from src.models.database import init_database, session_scope
from src.models.schema import Case, EvidenceItem, ImagingJob
from src.services.stats_service import (
    get_daily_job_counts,
    get_throughput_history,
    get_format_distribution,
    get_error_rate,
)


@pytest.fixture
def db_with_jobs(tmp_path):
    init_database(tmp_path / "stats.db")
    with session_scope() as s:
        c = Case(case_number="STATS-1", case_name="Stats")
        s.add(c)
        s.flush()
        ev = EvidenceItem(case_id=c.id, evidence_number="EV-S1")
        s.add(ev)
        s.flush()
        for i in range(5):
            status = "completed" if i < 3 else "failed"
            j = ImagingJob(
                evidence_id=ev.id,
                status=status,
                output_format="raw" if i % 2 == 0 else "e01",
                completed_at=datetime.now(timezone.utc),
                avg_speed_mbps=50.0 + i * 10,
                error_count=1 if status == "failed" else 0,
            )
            s.add(j)


def test_daily_job_counts(db_with_jobs):
    result = get_daily_job_counts(30)
    assert "dates" in result
    assert "completed" in result
    assert sum(result["completed"]) == 3


def test_throughput_history(db_with_jobs):
    result = get_throughput_history(50)
    assert "labels" in result
    assert "speeds" in result
    assert len(result["speeds"]) == 3


def test_format_distribution(db_with_jobs):
    result = get_format_distribution()
    assert isinstance(result, dict)
    total = sum(result.values())
    assert total == 5


def test_error_rate(db_with_jobs):
    result = get_error_rate()
    assert result["total"] == 5
    assert result["completed"] == 3
    assert result["with_errors"] == 2


def test_empty_db(tmp_path):
    init_database(tmp_path / "empty_stats.db")
    assert get_daily_job_counts()["dates"] == []
    assert get_throughput_history()["labels"] == []
    assert get_format_distribution() == {}


def test_error_rate_empty(tmp_path):
    init_database(tmp_path / "empty_rate.db")
    r = get_error_rate()
    assert r["total"] == 0
    assert r["success_rate"] == 0
