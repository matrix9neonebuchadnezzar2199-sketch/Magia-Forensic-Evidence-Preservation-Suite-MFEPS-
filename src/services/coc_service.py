"""
MFEPS v2.0 — CoC (Chain of Custody) サービス / ハッシュ検証サービス
"""
import csv
import io
import json
import logging
import uuid
from typing import Optional

from src.models.database import session_scope
from src.models.schema import ChainOfCustody, HashRecord
from src.utils.config import get_config

logger = logging.getLogger("mfeps.coc_service")


class CoCService:
    """Chain of Custody 管理"""

    def add_entry(self, evidence_id: str, action: str,
                  actor_name: str, description: str = "",
                  hash_snapshot: dict = None) -> str:
        try:
            with session_scope() as session:
                entry = ChainOfCustody(
                    id=str(uuid.uuid4()),
                    evidence_id=evidence_id,
                    action=action,
                    actor_name=actor_name,
                    description=description,
                    hash_snapshot=json.dumps(hash_snapshot or {}),
                )
                session.add(entry)
                logger.info(f"CoC エントリ追加: {action} by {actor_name}")
                return entry.id
        except Exception as e:
            logger.error(f"CoC エントリ追加失敗: {e}")
            raise

    def get_entries(self, evidence_id: str) -> list[dict]:
        with session_scope() as session:
            entries = session.query(ChainOfCustody).filter_by(
                evidence_id=evidence_id).order_by(
                ChainOfCustody.timestamp.asc()).all()
            return [
                {
                    "id": e.id,
                    "action": e.action,
                    "actor_name": e.actor_name,
                    "description": e.description,
                    "hash_snapshot": e.hash_snapshot,
                    "timestamp": str(e.timestamp),
                }
                for e in entries
            ]

    def export(self, evidence_id: str, format: str = "json") -> str:
        entries = self.get_entries(evidence_id)
        if format == "json":
            return json.dumps(entries, indent=2, ensure_ascii=False)
        output = io.StringIO()
        if entries:
            writer = csv.DictWriter(output, fieldnames=entries[0].keys())
            writer.writeheader()
            writer.writerows(entries)
        return output.getvalue()


class HashService:
    """ハッシュ検証 + RFC3161 タイムスタンプ"""

    def verify_hash(self, job_id: str) -> dict:
        """既存ジョブのハッシュを再検証"""
        with session_scope() as session:
            source = session.query(HashRecord).filter_by(
                job_id=job_id, target="source").first()
            verify = session.query(HashRecord).filter_by(
                job_id=job_id, target="verify").first()

            if not source or not verify:
                return {"status": "incomplete", "message": "ハッシュ記録が不完全です"}

            result = {
                "md5_match": source.md5 == verify.md5,
                "sha256_match": source.sha256 == verify.sha256,
            }
            if (source.sha1 or verify.sha1):
                result["sha1_match"] = source.sha1 == verify.sha1
            if (getattr(source, "sha512", "") or getattr(verify, "sha512", "")):
                result["sha512_match"] = source.sha512 == verify.sha512
            result["all_match"] = all(
                v for k, v in result.items() if k.endswith("_match")
            )
            return result

    def get_rfc3161_timestamp(self, digest: bytes,
                            algorithm: str = "sha256") -> Optional[bytes]:
        """RFC3161 タイムスタンプ取得（オプション）"""
        config = get_config()
        if not config.mfeps_rfc3161_enabled:
            return None

        try:
            import rfc3161ng
            stamper = rfc3161ng.RemoteTimestamper(
                config.mfeps_rfc3161_tsa_url,
                hashname=algorithm)
            token = stamper.timestamp(digest=digest)
            logger.info("RFC3161 タイムスタンプ取得成功")
            return token
        except ImportError:
            logger.warning("rfc3161ng 未インストール")
            return None
        except Exception as e:
            logger.warning(f"RFC3161 タイムスタンプ取得失敗: {e}")
            return None
