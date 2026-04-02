"""監査ログのハッシュチェーン整合性テスト"""

from src.services.audit_service import AuditService


class TestAuditHashChain:
    def test_single_entry_valid(self, audit_service: AuditService):
        audit_service.add_entry("INFO", "system", "テスト", "detail")
        result = audit_service.verify_chain()
        assert result["valid"] is True
        assert result["total_entries"] == 1

    def test_multiple_entries_valid(self, audit_service: AuditService):
        for i in range(10):
            audit_service.add_entry(
                "INFO", "system", f"エントリ {i}", ""
            )
        result = audit_service.verify_chain()
        assert result["valid"] is True
        assert result["total_entries"] == 10

    def test_empty_chain_valid(self, audit_service: AuditService):
        result = audit_service.verify_chain()
        assert result["valid"] is True
        assert result["total_entries"] == 0
