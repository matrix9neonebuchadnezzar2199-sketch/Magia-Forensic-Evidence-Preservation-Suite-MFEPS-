"""
MFEPS v2.1.0 — ログインページ
"""
import json

from nicegui import ui

from src.services.audit_service import get_audit_service
from src.services.auth_service import get_auth_service
from src.ui.session_auth import clear_session, is_authenticated, login_user
from src.ui.theme.modern_dark import CUSTOM_CSS


def build_login_page():
    """ログイン画面（レイアウトなし）"""
    ui.dark_mode(True)
    ui.add_head_html(f"<style>{CUSTOM_CSS}</style>")

    if is_authenticated():
        ui.navigate.to("/")
        return

    with ui.column().classes("absolute-center items-center q-pa-md"):
        with ui.card().classes("q-pa-xl").style("min-width: 360px;"):
            ui.label("🔬 MFEPS").classes("text-h5 text-weight-bold q-mb-sm")
            ui.label("ログインが必要です").classes("text-body2 text-grey-5 q-mb-lg")

            username_in = ui.input("ユーザー名").props("autofocus").classes("full-width")
            password_in = ui.input("パスワード", password=True, password_toggle_button=True).classes(
                "full-width q-mt-sm"
            )

            err_label = ui.label("").classes("text-negative text-caption q-mt-sm")

            async def do_login():
                err_label.text = ""
                auth = get_auth_service()
                audit = get_audit_service()
                u = (username_in.value or "").strip()
                p = password_in.value or ""
                if not u or not p:
                    err_label.text = "ユーザー名とパスワードを入力してください"
                    return
                user = auth.authenticate(u, p)
                if user:
                    login_user(user)
                    audit.add_entry(
                        "INFO",
                        "auth",
                        f"ログイン成功: {user['username']}",
                        json.dumps({"username": user["username"]}, ensure_ascii=False),
                    )
                    ui.navigate.to("/")
                else:
                    audit.add_entry(
                        "WARN",
                        "auth",
                        f"ログイン失敗: {u}",
                        json.dumps({"username": u}, ensure_ascii=False),
                    )
                    err_label.text = "ユーザー名またはパスワードが正しくありません"

            ui.button("ログイン", on_click=do_login, color="primary").classes(
                "full-width q-mt-lg"
            ).props("unelevated")
