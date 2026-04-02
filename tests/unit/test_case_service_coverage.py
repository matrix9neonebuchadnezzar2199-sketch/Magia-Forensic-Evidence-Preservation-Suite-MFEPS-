"""case_service.py のカバレッジ補完"""

import pytest

from src.models.database import init_database
from src.services.case_service import CaseService, EvidenceService


@pytest.fixture
def db(tmp_path):
    init_database(tmp_path / "case_cov.db")
    return tmp_path


def test_create_case(db):
    svc = CaseService()
    cid = svc.create_case("CASE-COV-1", "Coverage Case", "Examiner A")
    assert cid is not None


def test_get_or_create_case_existing(db):
    svc = CaseService()
    cid1 = svc.get_or_create_case("CASE-COV-2", "Test")
    cid2 = svc.get_or_create_case("CASE-COV-2")
    assert cid1 == cid2


def test_get_all_cases(db):
    svc = CaseService()
    svc.create_case("CASE-ALL-1", "All 1")
    svc.create_case("CASE-ALL-2", "All 2")
    cases = svc.get_all_cases()
    assert len(cases) >= 2


def test_get_case(db):
    svc = CaseService()
    cid = svc.create_case("CASE-GET-1", "Get Test")
    case = svc.get_case(cid)
    assert case["case_number"] == "CASE-GET-1"


def test_delete_case(db):
    svc = CaseService()
    cid = svc.create_case("CASE-DEL-1", "Del Test")
    assert svc.delete_case(cid)
    assert svc.get_case(cid) is None


def test_evidence_crud(db):
    case_svc = CaseService()
    ev_svc = EvidenceService()
    cid = case_svc.create_case("CASE-EV-1", "Ev Test")
    eid = ev_svc.create_evidence(cid, "EV-001", media_type="usb_hdd")
    assert eid is not None
    items = ev_svc.get_evidence_by_case(cid)
    assert len(items) == 1
    assert ev_svc.delete_evidence(eid)
