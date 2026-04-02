"""
MFEPS v2.1.0 — 案件管理 / 証拠品管理サービス
"""
import logging
from typing import Optional

from sqlalchemy.exc import IntegrityError

from src.models.database import session_scope
from src.models.schema import Case, EvidenceItem

logger = logging.getLogger("mfeps.case_service")


class CaseService:
    """案件 CRUD"""

    def create_case(self, case_number: str, case_name: str,
                    examiner_name: str = "", description: str = "") -> str:
        try:
            with session_scope() as session:
                case = Case(
                    case_number=case_number,
                    case_name=case_name,
                    examiner_name=examiner_name,
                    description=description,
                )
                session.add(case)
                session.flush()
                logger.info(f"案件作成: {case_number} - {case_name}")
                return case.id
        except Exception as e:
            logger.error(f"案件作成失敗: {e}")
            raise

    def get_or_create_case(self, case_number: str, case_name: str = "") -> str:
        """案件番号からIDを取得。存在しない場合は自動作成してIDを返す"""
        try:
            with session_scope() as session:
                case = session.query(Case).filter_by(case_number=case_number).first()
                if case:
                    return case.id

                case = Case(
                    case_number=case_number,
                    case_name=case_name or f"案件 {case_number}",
                )
                session.add(case)
                session.flush()
                logger.info(f"案件自動作成: {case_number}")
                return case.id
        except IntegrityError:
            with session_scope() as session:
                case = session.query(Case).filter_by(case_number=case_number).first()
                if case:
                    return case.id
            raise
        except Exception as e:
            logger.error(f"案件自動作成失敗: {e}")
            raise

    def get_all_cases(self) -> list[dict]:
        with session_scope() as session:
            cases = session.query(Case).order_by(Case.created_at.desc()).all()
            return [
                {
                    "id": c.id, "case_number": c.case_number,
                    "case_name": c.case_name, "examiner_name": c.examiner_name,
                    "status": c.status, "created_at": str(c.created_at),
                    "evidence_count": len(c.evidence_items),
                }
                for c in cases
            ]

    def get_case(self, case_id: str) -> Optional[dict]:
        with session_scope() as session:
            case = session.get(Case, case_id)
            if case:
                return {
                    "id": case.id, "case_number": case.case_number,
                    "case_name": case.case_name, "examiner_name": case.examiner_name,
                    "description": case.description, "status": case.status,
                    "created_at": str(case.created_at),
                }
            return None

    def delete_case(self, case_id: str) -> bool:
        try:
            with session_scope() as session:
                case = session.get(Case, case_id)
                if case:
                    session.delete(case)
                    logger.info(f"案件削除: {case.case_number}")
                    return True
                return False
        except Exception as e:
            logger.error(f"案件削除失敗: {e}")
            return False


class EvidenceService:
    """証拠品 CRUD"""

    def create_evidence(self, case_id: str, evidence_number: str,
                        media_type: str = "", device_model: str = "",
                        device_serial: str = "", capacity_bytes: int = 0,
                        description: str = "") -> str:
        try:
            with session_scope() as session:
                ev = EvidenceItem(
                    case_id=case_id,
                    evidence_number=evidence_number,
                    media_type=media_type,
                    device_model=device_model,
                    device_serial=device_serial,
                    device_capacity_bytes=capacity_bytes,
                    description=description,
                )
                session.add(ev)
                session.flush()
                logger.info(f"証拠品作成: {evidence_number}")
                return ev.id
        except Exception as e:
            logger.error(f"証拠品作成失敗: {e}")
            raise

    def get_or_create_evidence(self, case_id: str, evidence_number: str,
                               media_type: str = "", device_model: str = "",
                               device_serial: str = "", capacity_bytes: int = 0) -> str:
        """証拠品番号からIDを取得。存在しない場合は自動作成してIDを返す"""
        try:
            with session_scope() as session:
                ev = session.query(EvidenceItem).filter_by(
                    case_id=case_id, evidence_number=evidence_number).first()
                if ev:
                    return ev.id

                ev = EvidenceItem(
                    case_id=case_id,
                    evidence_number=evidence_number,
                    media_type=media_type,
                    device_model=device_model,
                    device_serial=device_serial,
                    device_capacity_bytes=capacity_bytes,
                )
                session.add(ev)
                session.flush()
                logger.info(f"証拠品自動作成: {evidence_number}")
                return ev.id
        except IntegrityError:
            with session_scope() as session:
                ev = session.query(EvidenceItem).filter_by(
                    case_id=case_id, evidence_number=evidence_number
                ).first()
                if ev:
                    return ev.id
            raise
        except Exception as e:
            logger.error(f"証拠品自動作成失敗: {e}")
            raise

    def get_evidence_by_case(self, case_id: str) -> list[dict]:
        with session_scope() as session:
            items = session.query(EvidenceItem).filter_by(
                case_id=case_id).order_by(EvidenceItem.created_at.desc()).all()
            return [
                {
                    "id": i.id, "evidence_number": i.evidence_number,
                    "media_type": i.media_type, "device_model": i.device_model,
                    "device_serial": i.device_serial,
                    "capacity_bytes": i.device_capacity_bytes,
                    "created_at": str(i.created_at),
                }
                for i in items
            ]

    def delete_evidence(self, evidence_id: str) -> bool:
        try:
            with session_scope() as session:
                ev = session.get(EvidenceItem, evidence_id)
                if ev:
                    session.delete(ev)
                    return True
                return False
        except Exception as e:
            logger.error(f"証拠品削除失敗: {e}")
            return False
