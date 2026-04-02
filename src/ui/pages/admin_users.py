"""
MFEPS v2.2.0 — ユーザー管理画面 (admin 専用)
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from nicegui import ui

from src.models.database import session_scope
from src.models.schema import User
from src.services.audit_service import get_audit_service
from src.services.auth_service import get_auth_service
from src.utils.audit_categories import AuditCategories
from src.utils.rbac import has_permission, require_role

logger = logging.getLogger("mfeps.ui.admin_users")


def build_admin_users_page():
    """ユーザー管理画面"""
    if not has_permission("admin"):
        ui.label("このページを表示する権限がありません").classes("text-negative")
        return

    ui.label("👥 ユーザー管理").classes("text-h5 text-weight-bold q-mb-md")

    body = ui.column().classes("full-width")

    def refresh():
        body.clear()
        with body:
            with session_scope() as session:
                rows = []
                for x in session.query(User).order_by(User.created_at).all():
                    rows.append(
                        {
                            "id": x.id,
                            "username": x.username,
                            "display_name": x.display_name or "",
                            "role": x.role,
                            "is_active": bool(
                                getattr(x, "is_active", True)
                            ),
                            "last_login": x.last_login_at,
                        }
                    )
            for r in rows:
                _user_row(r, refresh)

    refresh()

    ui.separator().classes("q-my-md")
    ui.label("新規ユーザー作成").classes("text-subtitle1 text-weight-bold")

    new_username = ui.input("ユーザー名").classes("q-mt-sm full-width")
    new_display = ui.input("表示名").classes("full-width")
    new_password = ui.input(
        "パスワード", password=True, password_toggle_button=True
    ).classes("full-width")
    new_role = ui.select(
        options=["admin", "examiner", "viewer"],
        value="examiner",
        label="ロール",
    ).classes("full-width")

    @require_role("admin")
    async def create_user():
        uname = (new_username.value or "").strip()
        pw = (new_password.value or "").strip()
        if not uname or not pw:
            ui.notify("ユーザー名とパスワードを入力してください", type="warning")
            return
        if len(pw) < 8:
            ui.notify("パスワードは8文字以上", type="warning")
            return
        try:
            auth = get_auth_service()
            with session_scope() as session:
                existing = session.query(User).filter(
                    User.username == uname
                ).first()
                if existing:
                    ui.notify(f"ユーザー '{uname}' は既に存在します", type="negative")
                    return
                session.add(
                    User(
                        username=uname,
                        password_hash=auth.hash_password(pw),
                        display_name=(new_display.value or "").strip() or uname,
                        role=new_role.value or "examiner",
                        is_active=True,
                    )
                )
            get_audit_service().add_entry(
                level="INFO",
                category=AuditCategories.SYSTEM,
                message=f"ユーザー作成: {uname} (role={new_role.value})",
                detail="",
            )
            ui.notify(f"ユーザー '{uname}' を作成しました", type="positive")
            new_username.value = ""
            new_display.value = ""
            new_password.value = ""
            refresh()
        except Exception as e:
            logger.exception("ユーザー作成失敗")
            ui.notify(f"作成失敗: {e}", type="negative")

    ui.button(
        "作成",
        on_click=create_user,
        color="primary",
        icon="person_add",
    ).props("unelevated").classes("q-mt-md")


def _user_row(row: dict[str, Any], refresh: Callable[[], None]) -> None:
    uid = row["id"]
    uname = row["username"]
    urole = row["role"]

    with ui.card().classes("q-pa-sm full-width q-mb-sm"):
        with ui.row().classes("items-center justify-between full-width wrap"):
            ui.label(uname).classes("text-weight-bold")
            ui.label(str(urole)).classes("text-caption text-grey-5")
        ui.label(f"表示名: {row['display_name'] or '—'}").classes("text-caption")
        ui.label(
            f"最終ログイン: {row['last_login'] or '未ログイン'}"
        ).classes("text-caption")

        def on_active_change(e):
            active = bool(e.sender.value)
            try:
                with session_scope() as session:
                    u = session.get(User, uid)
                    if u:
                        u.is_active = active
                get_audit_service().add_entry(
                    level="INFO",
                    category=AuditCategories.SYSTEM,
                    message=f"ユーザー有効化切替: {uname} → {active}",
                    detail="",
                )
                ui.notify("更新しました", type="positive")
            except Exception as ex:
                ui.notify(f"更新失敗: {ex}", type="negative")
            refresh()

        ui.switch(
            "アカウント有効",
            value=row["is_active"],
            on_change=on_active_change,
        )

        async def change_role():
            with ui.dialog() as dlg, ui.card():
                ui.label(f"ロール変更: {uname}").classes("text-h6")
                sel = ui.select(
                    options=["admin", "examiner", "viewer"],
                    value=urole,
                )

                async def save():
                    nr = sel.value
                    try:
                        with session_scope() as session:
                            u = session.get(User, uid)
                            if u:
                                u.role = nr
                        get_audit_service().add_entry(
                            level="INFO",
                            category=AuditCategories.SYSTEM,
                            message=f"ロール変更: {uname} → {nr}",
                            detail="",
                        )
                        ui.notify(f"{uname} を {nr} に変更しました", type="positive")
                    except Exception as ex:
                        ui.notify(f"失敗: {ex}", type="negative")
                    dlg.close()
                    refresh()

                with ui.row().classes("q-mt-md"):
                    ui.button("保存", on_click=save, color="primary")
                    ui.button("キャンセル", on_click=dlg.close).props("flat")
            dlg.open()

        async def delete_user():
            if uname == "admin":
                ui.notify("admin ユーザーは削除できません", type="warning")
                return
            try:
                with session_scope() as session:
                    u = session.get(User, uid)
                    if u:
                        session.delete(u)
                get_audit_service().add_entry(
                    level="WARN",
                    category=AuditCategories.SYSTEM,
                    message=f"ユーザー削除: {uname}",
                    detail="",
                )
                ui.notify(f"{uname} を削除しました", type="positive")
                refresh()
            except Exception as ex:
                ui.notify(f"削除失敗: {ex}", type="negative")

        with ui.row().classes("gap-2 q-mt-sm"):
            ui.button(
                "ロール変更",
                on_click=change_role,
                icon="edit",
            ).props("dense outline size=sm")
            if uname != "admin":
                ui.button(
                    "削除",
                    on_click=delete_user,
                    icon="delete",
                    color="negative",
                ).props("dense outline size=sm")
