"""
MFEPS v2.0 — 監査ログサービス（ハッシュチェーン改竄検知付き）
"""
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.models.database import get_session
from src.models.schema import AuditLog
from src.utils.constants import GENESIS_HASH_INPUT

logger = logging.getLogger("mfeps.audit")


class AuditService:
    """ハッシュチェーン付き監査ログ"""

    def add_entry(self, level: str, category: str,
                  message: str, detail: str = "") -> None:
        """監査ログエントリを追加（ハッシュチェーン付き）"""
        session = get_session()
        try:
            # 前エントリのハッシュ取得
            last_entry = session.query(AuditLog).order_by(
                AuditLog.id.desc()).first()

            if last_entry:
                prev_hash = last_entry.entry_hash
            else:
                prev_hash = hashlib.sha256(
                    GENESIS_HASH_INPUT.encode()).hexdigest()

            # 現エントリのハッシュ計算
            timestamp = datetime.now(timezone.utc)
            hash_input = (f"{prev_hash}|{timestamp.isoformat()}|"
                         f"{level}|{category}|{message}|{detail}")
            entry_hash = hashlib.sha256(hash_input.encode()).hexdigest()

            entry = AuditLog(
                timestamp=timestamp,
                level=level,
                category=category,
                message=message,
                detail=detail,
                prev_hash=prev_hash,
                entry_hash=entry_hash,
            )
            session.add(entry)
            session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"監査ログ追加失敗: {e}")
        finally:
            session.close()

    def verify_chain(self) -> dict:
        """ハッシュチェーン全体を検証"""
        session = get_session()
        try:
            entries = session.query(AuditLog).order_by(AuditLog.id.asc()).all()

            if not entries:
                return {"valid": True, "total_entries": 0, "first_invalid_id": None}

            genesis_hash = hashlib.sha256(GENESIS_HASH_INPUT.encode()).hexdigest()
            expected_prev = genesis_hash

            for entry in entries:
                # prev_hash チェック
                if entry.prev_hash != expected_prev:
                    return {
                        "valid": False,
                        "total_entries": len(entries),
                        "first_invalid_id": entry.id,
                        "error": f"prev_hash不一致: entry #{entry.id}",
                    }

                # entry_hash 再計算
                hash_input = (f"{entry.prev_hash}|{entry.timestamp.isoformat()}|"
                             f"{entry.level}|{entry.category}|"
                             f"{entry.message}|{entry.detail}")
                computed_hash = hashlib.sha256(hash_input.encode()).hexdigest()

                if entry.entry_hash != computed_hash:
                    return {
                        "valid": False,
                        "total_entries": len(entries),
                        "first_invalid_id": entry.id,
                        "error": f"entry_hash改竄検出: entry #{entry.id}",
                    }

                expected_prev = entry.entry_hash

            return {"valid": True, "total_entries": len(entries), "first_invalid_id": None}

        finally:
            session.close()

    def get_entries(self, limit: int = 100, offset: int = 0,
                    level: str = None, category: str = None) -> list[dict]:
        """監査ログエントリ一覧取得"""
        session = get_session()
        try:
            query = session.query(AuditLog).order_by(AuditLog.id.desc())
            if level:
                query = query.filter(AuditLog.level == level)
            if category:
                query = query.filter(AuditLog.category == category)

            entries = query.offset(offset).limit(limit).all()
            return [
                {
                    "id": e.id,
                    "timestamp": str(e.timestamp),
                    "level": e.level,
                    "category": e.category,
                    "message": e.message,
                    "detail": e.detail,
                }
                for e in entries
            ]
        finally:
            session.close()

    def export_log(self, format: str = "json") -> str:
        """監査ログをエクスポート"""
        entries = self.get_entries(limit=10000)
        if format == "json":
            return json.dumps(entries, indent=2, ensure_ascii=False)
        else:  # CSV
            import csv, io
            output = io.StringIO()
            if entries:
                writer = csv.DictWriter(output, fieldnames=entries[0].keys())
                writer.writeheader()
                writer.writerows(entries)
            return output.getvalue()


# グローバルインスタンス
_audit_service: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
