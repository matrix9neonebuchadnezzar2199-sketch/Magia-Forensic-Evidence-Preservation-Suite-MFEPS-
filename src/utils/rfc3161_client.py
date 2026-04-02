"""
MFEPS v2.1.0 — RFC 3161 タイムスタンプクライアント
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from src.utils.config import get_config
from src.utils.error_codes import E5003

if TYPE_CHECKING:
    from src.models.schema import HashRecord

logger = logging.getLogger("mfeps.rfc3161")


class RFC3161Error(Exception):
    """RFC3161 操作に関するエラー"""


class RFC3161Client:
    """RFC 3161 TSA へのタイムスタンプリクエスト（rfc3161ng）。"""

    def __init__(self, tsa_url: Optional[str] = None, timeout: float = 30.0):
        cfg = get_config()
        self._tsa_url = (tsa_url or cfg.mfeps_rfc3161_tsa_url or "").strip()
        self._enabled = bool(cfg.mfeps_rfc3161_enabled)
        self._timeout = timeout

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def tsa_url(self) -> str:
        return self._tsa_url

    def request_timestamp(self, digest_hex: str, algo: str = "sha256") -> bytes:
        """ハッシュ（hex）に対する TSR バイト列を取得する。"""
        if not self._enabled:
            raise RFC3161Error("RFC3161 タイムスタンプは無効です")
        if not self._tsa_url:
            raise RFC3161Error("TSA URL が設定されていません")

        clean = (digest_hex or "").replace(" ", "").strip()
        if len(clean) % 2 != 0:
            raise RFC3161Error("ダイジェスト hex が不正です")

        try:
            digest_bytes = bytes.fromhex(clean)
        except ValueError as e:
            raise RFC3161Error("ダイジェスト hex の解析に失敗しました") from e

        try:
            import rfc3161ng
        except ImportError as e:
            raise RFC3161Error(
                "rfc3161ng がインストールされていません"
            ) from e

        try:
            stamper = rfc3161ng.RemoteTimestamper(
                self._tsa_url,
                hashname=algo.lower(),
                timeout=self._timeout,
            )
            token = stamper.timestamp(digest=digest_bytes)
        except RFC3161Error:
            raise
        except Exception as e:
            logger.error(
                "%s RFC3161 タイムスタンプ取得失敗: %s",
                E5003,
                e,
                exc_info=True,
            )
            raise RFC3161Error(f"TSA 接続失敗: {e}") from e

        if not token:
            raise RFC3161Error(f"TSA からの応答が空です: {self._tsa_url}")

        logger.info(
            "RFC3161 タイムスタンプ取得成功: TSA=%s, algo=%s",
            self._tsa_url,
            algo,
        )
        return token

    def apply_to_source_hash_record(self, hr: "HashRecord") -> None:
        """source HashRecord にトークンを格納する（失敗時はログのみ）。"""
        sha = (getattr(hr, "sha256", None) or "").strip()
        if not sha:
            return
        if not self._enabled:
            return
        try:
            token = self.request_timestamp(sha, algo="sha256")
            hr.rfc3161_token = token
            hr.rfc3161_tsa_url = self._tsa_url
        except RFC3161Error as e:
            logger.warning("RFC3161 タイムスタンプ取得スキップ: %s", e)
