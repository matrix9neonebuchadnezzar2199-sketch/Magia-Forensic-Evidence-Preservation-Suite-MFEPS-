"""
MFEPS v2.0 — Enum 定義
"""
from enum import Enum


class MediaType(str, Enum):
    USB_HDD = "usb_hdd"
    CD = "cd"
    DVD = "dvd"
    BD = "bd"


class JobStatus(str, Enum):
    PENDING = "pending"
    SCANNING = "scanning"
    IMAGING = "imaging"
    HASHING = "hashing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HashTarget(str, Enum):
    SOURCE = "source"
    IMAGE = "image"
    VERIFY = "verify"


class MatchResult(str, Enum):
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    PENDING = "pending"


class CocAction(str, Enum):
    CREATED = "created"
    IMAGED = "imaged"
    VERIFIED = "verified"
    EXPORTED = "exported"
    TRANSFERRED = "transferred"


class CopyGuardType(str, Enum):
    NONE = "none"
    CSS = "css"
    REGION = "region"
    MACROVISION = "macrovision"
    UOP = "uop"
    ARCCOS = "arccos"
    DISNEY_XPROJECT = "disney_xproject"
    AACS = "aacs"
    BD_PLUS = "bd_plus"
    CINAVIA = "cinavia"
    CCCD = "cccd"
    UNKNOWN = "unknown"


class AuditLevel(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditCategory(str, Enum):
    SYSTEM = "system"
    IMAGING = "imaging"
    HASH = "hash"
    COC = "coc"
    AUTH = "auth"
    CONFIG = "config"


class CaseStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class OutputFormat(str, Enum):
    RAW = "raw"
    ISO = "iso"
