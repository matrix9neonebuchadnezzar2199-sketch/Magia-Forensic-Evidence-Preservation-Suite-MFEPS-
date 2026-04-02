"""
MFEPS v2.2.0 — 監査ログ外部転送
Syslog (UDP/TCP) および JSON Lines ファイルへのリアルタイムエクスポート
"""
import json
import logging
import logging.handlers
import socket
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mfeps.audit_exporter")


class AuditExporter:
    """
    AuditService.add_entry() から呼び出され、
    エントリを外部の Syslog / JSONL に転送する。
    """

    def __init__(
        self,
        syslog_host: Optional[str] = None,
        syslog_port: int = 514,
        syslog_proto: str = "udp",
        jsonl_path: Optional[Path] = None,
    ):
        self._syslog_handler: Optional[logging.handlers.SysLogHandler] = None
        self._jsonl_path = jsonl_path
        self._jsonl_lock = threading.Lock()

        if syslog_host and syslog_host.strip():
            try:
                st = (
                    socket.SOCK_DGRAM
                    if syslog_proto.lower() == "udp"
                    else socket.SOCK_STREAM
                )
                self._syslog_handler = logging.handlers.SysLogHandler(
                    address=(syslog_host.strip(), int(syslog_port)),
                    socktype=st,
                )
                self._syslog_handler.setFormatter(
                    logging.Formatter("MFEPS: %(message)s")
                )
                logger.info(
                    "Syslog エクスポート有効: %s:%d (%s)",
                    syslog_host,
                    syslog_port,
                    syslog_proto,
                )
            except OSError as e:
                logger.error("Syslog 初期化失敗: %s", e)

        if jsonl_path:
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info("JSONL エクスポート有効: %s", jsonl_path)

    def export(
        self,
        level: str,
        category: str,
        message: str,
        detail: str,
        entry_hash: str,
        prev_hash: str,
    ) -> None:
        """エントリを外部に転送"""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "category": category,
            "message": message,
            "detail": detail,
            "entry_hash": entry_hash,
            "prev_hash": prev_hash,
            "source": "MFEPS",
        }

        if self._syslog_handler:
            try:
                log_record = logging.LogRecord(
                    name="mfeps.audit",
                    level=logging.INFO,
                    pathname="",
                    lineno=0,
                    msg=json.dumps(record, ensure_ascii=False),
                    args=(),
                    exc_info=None,
                )
                self._syslog_handler.emit(log_record)
            except OSError as e:
                logger.warning("Syslog 送信失敗: %s", e)

        if self._jsonl_path:
            try:
                with self._jsonl_lock:
                    with open(
                        self._jsonl_path, "a", encoding="utf-8"
                    ) as f:
                        f.write(
                            json.dumps(record, ensure_ascii=False) + "\n"
                        )
            except OSError as e:
                logger.warning("JSONL 書き込み失敗: %s", e)

    def close(self) -> None:
        if self._syslog_handler:
            self._syslog_handler.close()


_exporter: Optional[AuditExporter] = None
_exporter_lock = threading.Lock()


def get_audit_exporter() -> Optional[AuditExporter]:
    """設定に基づきエクスポータをシングルトン取得（無効時は None）。"""
    global _exporter
    if _exporter is not None:
        return _exporter
    with _exporter_lock:
        if _exporter is not None:
            return _exporter
        from src.utils.config import get_config

        cfg = get_config()
        host = (cfg.mfeps_syslog_host or "").strip()
        jsonl: Optional[Path] = None
        if cfg.mfeps_audit_jsonl_enabled:
            raw = (cfg.mfeps_audit_jsonl_path or "").strip()
            if raw:
                p = Path(raw)
                if not p.is_absolute():
                    p = cfg.base_dir / p
                jsonl = p.resolve()

        if not host and not jsonl:
            return None

        _exporter = AuditExporter(
            syslog_host=host or None,
            syslog_port=cfg.mfeps_syslog_port,
            syslog_proto=cfg.mfeps_syslog_proto or "udp",
            jsonl_path=jsonl,
        )
    return _exporter


def reset_audit_exporter_for_tests() -> None:
    global _exporter
    with _exporter_lock:
        if _exporter:
            _exporter.close()
        _exporter = None
