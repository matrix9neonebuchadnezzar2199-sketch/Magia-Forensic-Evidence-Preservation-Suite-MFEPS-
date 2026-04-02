"""ケース管理のデータ層テスト"""
import pytest

from src.models.database import init_database
from src.services.case_service import CaseService, EvidenceService


@pytest.fixture
def db(tmp_path):
    init_database(tmp_path / "cases_ui.db")


def test_create_and_list(db):
    svc = CaseService()
    svc.create_case("UI-001", "UI Test Case", "Tester")
    cases = svc.get_all_cases()
    assert len(cases) == 1
    assert cases[0]["case_number"] == "UI-001"


def test_evidence_in_case(db):
    case_svc = CaseService()
    ev_svc = EvidenceService()
    cid = case_svc.create_case("UI-002", "Evidence Test")
    ev_svc.create_evidence(cid, "EV-UI-1", media_type="usb_hdd")
    ev_svc.create_evidence(cid, "EV-UI-2", media_type="dvd")
    items = ev_svc.get_evidence_by_case(cid)
    assert len(items) == 2


def test_delete_case_cascades(db):
    case_svc = CaseService()
    ev_svc = EvidenceService()
    cid = case_svc.create_case("UI-DEL", "Delete Test")
    ev_svc.create_evidence(cid, "EV-DEL-1")
    assert case_svc.delete_case(cid)
    assert ev_svc.get_evidence_by_case(cid) == []


def test_get_nonexistent_case(db):
    svc = CaseService()
    assert svc.get_case("nonexistent-id") is None


def test_delete_nonexistent_case(db):
    svc = CaseService()
    assert not svc.delete_case("nonexistent-id")


def test_get_or_create_case_returns_existing(db):
    svc = CaseService()
    id1 = svc.create_case("GC-1", "First")
    id2 = svc.get_or_create_case("GC-1", "Other Name")
    assert id1 == id2


def test_get_or_create_evidence_returns_existing(db):
    case_svc = CaseService()
    ev_svc = EvidenceService()
    cid = case_svc.create_case("GC-2", "E")
    e1 = ev_svc.create_evidence(cid, "EV-SAME")
    e2 = ev_svc.get_or_create_evidence(cid, "EV-SAME")
    assert e1 == e2
