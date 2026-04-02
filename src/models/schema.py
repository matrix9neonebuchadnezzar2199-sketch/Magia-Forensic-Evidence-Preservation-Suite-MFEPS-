"""
MFEPS v2.1.0 — SQLAlchemy ORM モデル定義
8テーブル: users, cases, evidence_items, imaging_jobs, hash_records,
chain_of_custody, audit_log, app_settings
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, BigInteger, Float, DateTime, Boolean, LargeBinary,
    ForeignKey, Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    """WebUI ログインユーザー"""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(200), default="")
    role = Column(String(20), default="examiner")  # admin / examiner / viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    last_login_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User {self.username}>"


class Case(Base):
    """案件テーブル"""
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    case_number = Column(String(100), unique=True, nullable=False)
    case_name = Column(String(200), nullable=False)
    examiner_name = Column(String(100), default="")
    description = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    status = Column(String(20), default="active")  # active / closed / archived

    evidence_items = relationship("EvidenceItem", back_populates="case", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Case {self.case_number}: {self.case_name}>"


class EvidenceItem(Base):
    """証拠品テーブル"""
    __tablename__ = "evidence_items"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    evidence_number = Column(String(100), nullable=False)
    media_type = Column(String(20))  # usb_hdd / cd / dvd / bd
    device_model = Column(String(200), default="")
    device_serial = Column(String(200), default="")
    device_capacity_bytes = Column(BigInteger, default=0)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)

    case = relationship("Case", back_populates="evidence_items")
    imaging_jobs = relationship("ImagingJob", back_populates="evidence", cascade="all, delete-orphan")
    coc_entries = relationship("ChainOfCustody", back_populates="evidence", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Evidence {self.evidence_number}>"


class ImagingJob(Base):
    """イメージング作業テーブル"""
    __tablename__ = "imaging_jobs"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    evidence_id = Column(String(36), ForeignKey("evidence_items.id"), nullable=False)
    status = Column(String(20), default="pending")
    source_path = Column(String(500), default="")
    output_path = Column(String(500), default="")
    output_format = Column(String(20), default="raw")
    total_bytes = Column(BigInteger, default=0)
    copied_bytes = Column(BigInteger, default=0)
    buffer_size = Column(Integer, default=1_048_576)
    error_count = Column(Integer, default=0)
    error_map_path = Column(String(500), default="")
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    elapsed_seconds = Column(Float, default=0.0)
    avg_speed_mbps = Column(Float, default=0.0)
    copy_guard_type = Column(String(100), default="")
    copy_guard_detail = Column(Text, default="")  # JSON
    write_block_method = Column(String(20), default="none")  # none / software / hardware / both
    notes = Column(Text, default="")

    # E01 (ewfacquire) — Phase 1
    e01_compression = Column(String(40), default="")
    e01_segment_size_bytes = Column(BigInteger, default=0)
    e01_ewf_format = Column(String(20), default="")
    e01_examiner_name = Column(String(200), default="")
    e01_notes = Column(Text, default="")
    e01_command_line = Column(Text, default="")
    e01_ewfacquire_version = Column(String(100), default="")
    e01_segment_count = Column(Integer, default=0)
    e01_log_path = Column(String(500), default="")

    evidence = relationship("EvidenceItem", back_populates="imaging_jobs")
    hash_records = relationship("HashRecord", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ImagingJob {self.id[:8]} status={self.status}>"


class HashRecord(Base):
    """ハッシュ記録テーブル"""
    __tablename__ = "hash_records"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    job_id = Column(String(36), ForeignKey("imaging_jobs.id"), nullable=False)
    target = Column(String(20), default="source")  # source / image / verify
    md5 = Column(String(32), default="")
    sha1 = Column(String(40), default="")
    sha256 = Column(String(64), default="")
    sha512 = Column(String(128), default="")
    calculated_at = Column(DateTime, default=_utcnow)
    match_result = Column(String(20), default="pending")
    rfc3161_token = Column(LargeBinary, nullable=True)
    rfc3161_tsa_url = Column(String(500), default="")

    job = relationship("ImagingJob", back_populates="hash_records")

    def __repr__(self):
        return f"<HashRecord {self.target} md5={self.md5[:8]}...>"


class ChainOfCustody(Base):
    """証拠管理連鎖テーブル"""
    __tablename__ = "chain_of_custody"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    evidence_id = Column(String(36), ForeignKey("evidence_items.id"), nullable=False)
    action = Column(String(30), default="created")
    actor_name = Column(String(100), default="")
    description = Column(Text, default="")
    hash_snapshot = Column(Text, default="")  # JSON
    timestamp = Column(DateTime, default=_utcnow)

    evidence = relationship("EvidenceItem", back_populates="coc_entries")

    def __repr__(self):
        return f"<CoC {self.action} at {self.timestamp}>"


class AppSettings(Base):
    """アプリケーション設定（1行テーブル）"""

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, default=1)
    legal_consent_accepted = Column(Boolean, default=False)
    legal_consent_version = Column(String(20), default="")
    legal_consent_at = Column(DateTime, nullable=True)
    legal_consent_actor = Column(String(100), default="")


class AuditLog(Base):
    """監査ログテーブル（ハッシュチェーン改竄検知付き）"""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=_utcnow, index=True)
    # ハッシュ入力に使った正確な ISO 文字列（DB 往復で表現が変わるのを防ぐ）
    hash_timestamp_iso = Column(String(64), default="")
    level = Column(String(10), default="INFO")
    category = Column(String(20), default="system")
    message = Column(Text, default="")
    detail = Column(Text, default="")  # JSON
    prev_hash = Column(String(64), default="")
    entry_hash = Column(String(64), default="")

    __table_args__ = (
        Index("ix_audit_level_category", "level", "category"),
    )

    def __repr__(self):
        return f"<AuditLog #{self.id} [{self.level}] {self.message[:40]}>"
