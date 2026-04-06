"""default_identifiers"""
from src.utils.default_identifiers import (
    default_case_evidence_ids,
    optical_media_tag_for_default,
)


def test_default_case_evidence_ids_format():
    a, b = default_case_evidence_ids("USB")
    assert a == b
    assert len(a) >= 16
    assert "_USB" in a
    assert a[8] == "-"


def test_optical_media_tag():
    class A:
        media_type = "DVD-Video"

    class B:
        media_type = "CD-ROM"

    assert optical_media_tag_for_default(A()) == "DVD"
    assert optical_media_tag_for_default(B()) == "CD"
    assert optical_media_tag_for_default(None) == "DVD"
