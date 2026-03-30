"""
MFEPS v2.0 — メインレイアウト
ヘッダー + 折り畳みサイドバー + メインコンテンツ + ステータスバー
"""
from nicegui import ui, app
from src.utils.constants import APP_TITLE, COLOR_PRIMARY
from src.ui.theme.modern_dark import CUSTOM_CSS
from src.ui.session_auth import require_auth, clear_session
from src.services.audit_service import get_audit_service
import json


def create_layout(content_builder):
    """メインレイアウトを構築"""

    if not require_auth():
        return

    # ---------- ダークモード設定 ----------
    ui.dark_mode(True)

    # ---------- カスタムCSS注入（ページレベル） ----------
    ui.add_head_html(f"<style>{CUSTOM_CSS}</style>")

    # ---------- ヘッダー ----------
    with ui.header(elevated=True).classes("items-center justify-between q-px-md"):
        # 左: ハンバーガー + タイトル
        with ui.row().classes("items-center gap-2"):
            ui.button(
                icon="menu", on_click=lambda: left_drawer.toggle()
            ).props("flat round dense color=white")
            ui.label("🔬 MFEPS").classes("text-h6 text-weight-bold")
            ui.label("Forensic Evidence Preservation Suite").classes(
                "text-caption text-grey-5 gt-sm")

        # 右: ユーザー・ログアウト・設定
        with ui.row().classes("items-center gap-2"):
            uname = app.storage.user.get("username", "")
            dname = app.storage.user.get("display_name", uname)
            ui.label(dname or "User").classes("text-caption text-grey-4 gt-xs")

            def _logout():
                audit = get_audit_service()
                audit.add_entry(
                    "INFO",
                    "auth",
                    f"ログアウト: {uname}",
                    json.dumps({"username": uname}, ensure_ascii=False),
                )
                clear_session()
                ui.navigate.to("/login")

            ui.button("ログアウト", on_click=_logout).props(
                "flat dense no-caps color=white"
            ).classes("text-caption")

            ui.button(
                icon="settings",
                on_click=lambda: ui.navigate.to("/settings"),
            ).props("flat round dense color=white")

    # ---------- サイドバー ----------
    with ui.left_drawer(value=True, bordered=True).classes(
            "q-pa-none") as left_drawer:
        left_drawer.props("width=280 breakpoint=800")

        # ---- メディアコピー セクション ----
        ui.label("メディアコピー").classes("section-header")

        ui.button(
            "💾 USB・HDD",
            on_click=lambda: ui.navigate.to("/usb-hdd"),
            icon="usb"
        ).props("flat align=left").classes("full-width q-mx-sm")

        ui.button(
            "💿 CD・DVD・BD",
            on_click=lambda: ui.navigate.to("/optical"),
            icon="album"
        ).props("flat align=left").classes("full-width q-mx-sm")

        ui.separator().classes("q-my-sm")

        # ---- 管理 セクション ----
        ui.label("管理").classes("section-header")

        ui.button(
            "🏠 ダッシュボード",
            on_click=lambda: ui.navigate.to("/"),
            icon="dashboard"
        ).props("flat align=left").classes("full-width q-mx-sm")

        ui.button(
            "🔑 ハッシュ検証",
            on_click=lambda: ui.navigate.to("/hash-verify"),
            icon="verified_user"
        ).props("flat align=left").classes("full-width q-mx-sm")

        ui.button(
            "⛓️ Chain of Custody",
            on_click=lambda: ui.navigate.to("/coc"),
            icon="link"
        ).props("flat align=left").classes("full-width q-mx-sm")

        ui.button(
            "📄 レポート",
            on_click=lambda: ui.navigate.to("/reports"),
            icon="description"
        ).props("flat align=left").classes("full-width q-mx-sm")

        ui.button(
            "📋 監査ログ",
            on_click=lambda: ui.navigate.to("/audit"),
            icon="assignment"
        ).props("flat align=left").classes("full-width q-mx-sm")

        # ---- スペーサー + バージョン ----
        ui.space()
        with ui.row().classes("q-pa-md items-center"):
            ui.label("v2.0.0").classes("text-caption text-grey-6")

    # ---------- メインコンテンツ ----------
    with ui.column().classes("q-pa-lg full-width fade-in"):
        content_builder()

    # ---------- ステータスバー ----------
    with ui.footer().classes("q-pa-xs q-px-md text-caption"):
        with ui.row().classes("items-center gap-4"):
            ui.label("準備完了")
            ui.space()
            ui.label("MFEPS v2.0").classes("text-grey-6")

