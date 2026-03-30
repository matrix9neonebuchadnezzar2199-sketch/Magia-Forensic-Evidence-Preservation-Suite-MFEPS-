"""
NiceGUI クライアントセッション（app.storage.user）と認証状態
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from nicegui import app

from src.utils.config import get_config


def _parse_login_at(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, str):
        s = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def clear_session() -> None:
    app.storage.user.clear()


def is_authenticated() -> bool:
    u = app.storage.user
    if not u.get("user_id"):
        return False
    login_at = _parse_login_at(u.get("login_at"))
    if not login_at:
        clear_session()
        return False
    hours = float(get_config().session_timeout_hours)
    if datetime.now(timezone.utc) - login_at > timedelta(hours=hours):
        clear_session()
        return False
    return True


def login_user(user_dict: dict[str, Any]) -> None:
    """auth_service.authenticate の戻り値を格納"""
    now = datetime.now(timezone.utc)
    app.storage.user["user_id"] = user_dict["id"]
    app.storage.user["username"] = user_dict["username"]
    app.storage.user["display_name"] = user_dict.get("display_name") or user_dict["username"]
    app.storage.user["role"] = user_dict.get("role", "examiner")
    app.storage.user["login_at"] = now.isoformat()


def get_current_user_id() -> str | None:
    """現在のログインユーザー ID（未ログイン・セッション無効時は None）"""
    try:
        u = app.storage.user
    except Exception:
        return None
    if not u:
        return None
    uid = u.get("user_id")
    return str(uid) if uid else None


def get_current_actor_name() -> str:
    """CoC・監査用の表示名（未ログイン時はフォールバック）"""
    try:
        u = app.storage.user
        if u.get("display_name"):
            return str(u["display_name"])
        if u.get("username"):
            return str(u["username"])
    except Exception:
        pass
    return "MFEPS Auto"


def require_auth() -> bool:
    """
    認証済みなら True。
    未認証なら /login へ遷移し False（この場合はレイアウト描画を中断すること）。
    """
    from nicegui import ui

    if is_authenticated():
        return True
    ui.navigate.to("/login")
    return False
