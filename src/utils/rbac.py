"""
MFEPS v2.2.0 — ロールベースアクセス制御
"""
from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, TypeVar

from nicegui import app, ui

logger = logging.getLogger("mfeps.rbac")

_ROLE_HIERARCHY = {"admin": 3, "examiner": 2, "viewer": 1}

PAGE_PERMISSIONS = {
    "/": "viewer",
    "/usb-hdd": "examiner",
    "/optical": "examiner",
    "/hash-verify": "examiner",
    "/coc": "examiner",
    "/reports": "viewer",
    "/audit": "viewer",
    "/settings": "admin",
    "/admin/users": "admin",
}

ACTION_PERMISSIONS = {
    "imaging.start": "examiner",
    "imaging.cancel": "examiner",
    "report.generate": "examiner",
    "coc.add": "examiner",
    "settings.save": "admin",
    "settings.reset_db": "admin",
    "user.create": "admin",
    "user.delete": "admin",
    "user.change_role": "admin",
}


def _get_user_role() -> str:
    try:
        return app.storage.user.get("role", "viewer")
    except Exception:
        return "viewer"


def has_permission(required_role: str) -> bool:
    user_role = _get_user_role()
    user_level = _ROLE_HIERARCHY.get(user_role, 0)
    required_level = _ROLE_HIERARCHY.get(required_role, 99)
    return user_level >= required_level


def check_page_access(path: str) -> bool:
    required = PAGE_PERMISSIONS.get(path, "viewer")
    return has_permission(required)


def check_action(action: str) -> bool:
    required = ACTION_PERMISSIONS.get(action, "admin")
    return has_permission(required)


F = TypeVar("F", bound=Callable[..., Any])


def require_role(role: str) -> Callable[[F], F]:
    """関数実行前にロールチェック。権限不足時は通知して None を返す。"""

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def awrapper(*args: Any, **kwargs: Any) -> Any:
                if not has_permission(role):
                    ui.notify(
                        "この操作を行う権限がありません",
                        type="negative",
                    )
                    logger.warning(
                        "権限不足: role=%s, required=%s, action=%s",
                        _get_user_role(),
                        role,
                        func.__name__,
                    )
                    return None
                return await func(*args, **kwargs)

            return awrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def swrapper(*args: Any, **kwargs: Any) -> Any:
            if not has_permission(role):
                ui.notify(
                    "この操作を行う権限がありません",
                    type="negative",
                )
                logger.warning(
                    "権限不足: role=%s, required=%s, action=%s",
                    _get_user_role(),
                    role,
                    func.__name__,
                )
                return None
            return func(*args, **kwargs)

        return swrapper  # type: ignore[return-value]

    return decorator
