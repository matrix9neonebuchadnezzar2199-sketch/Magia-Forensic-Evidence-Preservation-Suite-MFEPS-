"""
MFEPS v2.1.0 — 認証サービス（bcrypt・ユーザー CRUD）
"""
from __future__ import annotations

import logging
import secrets
import threading
from datetime import datetime, timezone
from typing import Any, Optional

import bcrypt

from src.models.database import session_scope
from src.models.schema import User

logger = logging.getLogger("mfeps.auth")


class AuthService:
    """パスワード検証とユーザー参照"""

    @staticmethod
    def hash_password(plain: str) -> str:
        return bcrypt.hashpw(
            plain.encode("utf-8"), bcrypt.gensalt()
        ).decode("ascii")

    @staticmethod
    def verify_password(plain: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(
                plain.encode("utf-8"),
                password_hash.encode("ascii"),
            )
        except (ValueError, TypeError):
            return False

    def authenticate(self, username: str, password: str) -> Optional[dict[str, Any]]:
        """成功時はセッション用のユーザーディクトを返す"""
        with session_scope() as session:
            user = (
                session.query(User)
                .filter(User.username == username.strip())
                .first()
            )
            if not user:
                return None
            if not self.verify_password(password, user.password_hash):
                return None
            if not getattr(user, "is_active", True):
                logger.warning("無効化アカウントでログイン試行: %s", username)
                return None
            user.last_login_at = datetime.now(timezone.utc)
            return {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name or user.username,
                "role": user.role,
                "is_active": getattr(user, "is_active", True),
            }

    def get_user_by_id(self, user_id: str) -> Optional[dict[str, Any]]:
        """セッション外で安全に使えるプレーン dict を返す（ORM は返さない）"""
        with session_scope() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            return {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name or user.username,
                "role": user.role,
                "is_active": getattr(user, "is_active", True),
            }


_auth_service: Optional[AuthService] = None
_auth_service_lock = threading.Lock()


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is not None:
        return _auth_service
    with _auth_service_lock:
        if _auth_service is None:
            _auth_service = AuthService()
    return _auth_service


def ensure_default_admin() -> None:
    """
    ユーザーが 0 件のとき admin を 1 件作成し、ランダムパスワードをコンソールに表示する。
    """
    try:
        with session_scope() as session:
            count = session.query(User).count()
            if count > 0:
                return

            password = secrets.token_urlsafe(16)
            svc = AuthService()
            h = svc.hash_password(password)
            admin = User(
                username="admin",
                password_hash=h,
                display_name="Administrator",
                role="admin",
            )
            session.add(admin)

            banner = (
                "\n"
                + "=" * 60
                + "\n"
                "初回起動: デフォルト管理者アカウントを作成しました。\n"
                f"  ユーザー名: admin\n"
                f"  パスワード: {password}\n"
                "（このメッセージは初回のみ表示されます。必ず変更してください。）\n"
                + "=" * 60
                + "\n"
            )
            logger.warning(
                "初回起動: デフォルト管理者 admin を作成（パスワードはコンソール出力を参照）"
            )
            print(banner)
    except Exception as e:
        logger.error("ensure_default_admin 失敗: %s", e)
        raise
