"""Phase 3-3: audit category constants"""
from src.utils.audit_categories import AuditCategories


class TestAuditCategories:
    def test_unique_values(self):
        vals = [
            v
            for k, v in AuditCategories.__dict__.items()
            if not k.startswith("_") and isinstance(v, str)
        ]
        assert len(vals) == len(set(vals))

    def test_naming_snake(self):
        for k, v in AuditCategories.__dict__.items():
            if not k.startswith("_") and isinstance(v, str):
                assert v == v.lower()
                assert " " not in v
