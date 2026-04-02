"""CoC / HashService の軽量テスト"""
import json

import pytest

from src.models.database import get_session, init_database
from src.models.schema import Case, EvidenceItem, HashRecord, ImagingJob
from src.services.coc_service import CoCService, HashService


@pytest.fixture
def coc_db(tmp_path):
    init_database(tmp_path / "coc.db")
    session = get_session()
    case = Case(case_number="C-CoC", case_name="x", examiner_name="y")
    session.add(case)
    session.commit()
    ev = EvidenceItem(
        case_id=case.id, evidence_number="EV1", media_type="usb_hdd"
    )
    session.add(ev)
    session.commit()
    job = ImagingJob(
        evidence_id=ev.id,
        status="completed",
        source_path=r"\\.\X",
        total_bytes=1,
        copied_bytes=1,
        elapsed_seconds=1.0,
        avg_speed_mbps=1.0,
        error_count=0,
    )
    session.add(job)
    session.commit()
    session.add(
        HashRecord(
            job_id=job.id,
            target="source",
            md5="a",
            sha256="b",
            sha1="c",
        )
    )
    session.add(
        HashRecord(
            job_id=job.id,
            target="verify",
            md5="a",
            sha256="b",
            sha1="c",
            match_result="matched",
        )
    )
    session.commit()
    return {"evidence_id": ev.id, "job_id": job.id}


def test_coc_add_and_list(coc_db):
    svc = CoCService()
    eid = coc_db["evidence_id"]
    rid = svc.add_entry(eid, "sealed", "alice", "note", {"k": 1})
    assert rid
    rows = svc.get_entries(eid)
    assert len(rows) == 1
    assert rows[0]["action"] == "sealed"
    assert "k" in rows[0]["hash_snapshot"]


def test_coc_export_json_csv(coc_db):
    svc = CoCService()
    eid = coc_db["evidence_id"]
    svc.add_entry(eid, "x", "b")
    j = json.loads(svc.export(eid, "json"))
    assert isinstance(j, list)
    csv_out = svc.export(eid, "csv")
    assert "action" in csv_out


def test_hash_verify_match(coc_db):
    svc = HashService()
    r = svc.verify_hash(coc_db["job_id"])
    assert r["all_match"] is True


def test_hash_verify_incomplete(tmp_path):
    init_database(tmp_path / "h.db")
    session = get_session()
    case = Case(case_number="a", case_name="b", examiner_name="c")
    session.add(case)
    session.commit()
    ev = EvidenceItem(case_id=case.id, evidence_number="e", media_type="x")
    session.add(ev)
    session.commit()
    job = ImagingJob(
        evidence_id=ev.id,
        status="completed",
        source_path="p",
        total_bytes=1,
        copied_bytes=1,
        elapsed_seconds=1.0,
        avg_speed_mbps=1.0,
        error_count=0,
    )
    session.add(job)
    session.commit()
    session.add(HashRecord(job_id=job.id, target="source", md5="a"))
    session.commit()
    svc = HashService()
    r = svc.verify_hash(job.id)
    assert r["status"] == "incomplete"
