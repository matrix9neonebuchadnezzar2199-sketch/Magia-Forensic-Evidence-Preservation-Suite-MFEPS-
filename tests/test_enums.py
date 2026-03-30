"""Enum 定義の整合性テスト"""


def test_all_enums_importable():
    from src.models.enums import (
        MediaType,
        JobStatus,
        HashTarget,
        MatchResult,
        CocAction,
        CopyGuardType,
        AuditLevel,
        AuditCategory,
        CaseStatus,
        OutputFormat,
        WriteBlockMethod,
    )

    assert len(MediaType) >= 3
    assert len(CopyGuardType) >= 10
    assert WriteBlockMethod.BOTH.value == "both"


def test_write_block_method_values():
    from src.models.enums import WriteBlockMethod

    values = {m.value for m in WriteBlockMethod}
    assert values == {"none", "software", "hardware", "both"}
