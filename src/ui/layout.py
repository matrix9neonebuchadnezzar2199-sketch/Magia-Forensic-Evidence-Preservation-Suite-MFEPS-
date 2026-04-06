"""
MFEPS v2.1.0 — メインレイアウト
ヘッダー + 折り畳みサイドバー + メインコンテンツ + ステータスバー
"""
from nicegui import ui, app
from src.utils.storage_helpers import get_user_storage
from src.utils.config import get_config
from src.utils.constants import APP_BRAND_DISPLAY, APP_BRAND_TAGLINE, APP_NAME, APP_VERSION
from src.ui.theme.modern_dark import CUSTOM_CSS
from src.ui.theme.light_theme import LIGHT_CSS
from src.ui.session_auth import require_auth, clear_session
from src.services.audit_service import get_audit_service
from src.utils.rbac import check_page_access, has_permission
import json


def create_layout(page_path: str, content_builder):
    """メインレイアウトを構築"""

    if not require_auth():
        return
    if not check_page_access(page_path):
        ui.navigate.to("/")
        return

    # ---------- テーマ（ストレージ / 既定ダーク） ----------
    theme = app.storage.general.get("theme", "dark")
    if theme == "light":
        ui.dark_mode(False)
        ui.add_head_html(f"<style>{LIGHT_CSS}</style>")
        ui.run_javascript(
            'document.body.classList.add("mfeps-light")', timeout=3.0
        )
    else:
        ui.dark_mode(True)
        ui.add_head_html(f"<style>{CUSTOM_CSS}</style>")
        ui.run_javascript(
            'document.body.classList.remove("mfeps-light")', timeout=3.0
        )
    cfg = get_config()
    fs = int(app.storage.general.get("font_size", cfg.mfeps_font_size))
    ui.add_head_html(
        f"<style id=\"mfeps-font-persist\">"
        f"html, body, .nicegui-content {{ font-size: {fs}px !important; }}"
        f"</style>"
    )

    # ---------- ヘッダー ----------
    with ui.header(elevated=True).classes("items-center justify-between q-px-md"):
        # 左: ハンバーガー + タイトル
        with ui.row().classes("items-center gap-2"):
            ui.button(
                icon="menu", on_click=lambda: left_drawer.toggle()
            ).props("flat round dense color=white")
            ui.label(APP_BRAND_DISPLAY).classes("text-h6 text-weight-bolder").style(
                "letter-spacing: 0.08em"
            )
            ui.label(APP_BRAND_TAGLINE).classes("text-caption text-grey-5 gt-sm")

        # 右: ユーザー・ログアウト・設定
        with ui.row().classes("items-center gap-2"):
            u = get_user_storage()
            uname = u.get("username", "")
            dname = u.get("display_name", uname)
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

            if has_permission("admin"):
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

        if has_permission("examiner"):
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
            "📁 ケース管理",
            on_click=lambda: ui.navigate.to("/cases"),
            icon="folder",
        ).props("flat align=left").classes("full-width q-mx-sm")

        if has_permission("examiner"):
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

        if has_permission("admin"):
            ui.separator().classes("q-my-sm")
            ui.label("管理者").classes("section-header")
            ui.button(
                "⚙️ 設定",
                on_click=lambda: ui.navigate.to("/settings"),
                icon="settings",
            ).props("flat align=left").classes("full-width q-mx-sm")
            ui.button(
                "👥 ユーザー管理",
                on_click=lambda: ui.navigate.to("/admin/users"),
                icon="people",
            ).props("flat align=left").classes("full-width q-mx-sm")

        # ---- スペーサー + バージョン ----
        ui.space()
        with ui.row().classes("q-pa-md items-center"):
            ui.label(f"v{APP_VERSION}").classes("text-caption text-grey-6")

    # ---------- メインコンテンツ ----------
    with ui.column().classes("q-pa-lg full-width fade-in"):
        content_builder()

    # ---------- ステータスバー ----------
    with ui.footer().classes("q-pa-xs q-px-md text-caption"):
        with ui.row().classes("items-center gap-4"):
            ui.label("準備完了")
            ui.space()
            ui.label(f"{APP_NAME} v{APP_VERSION}").classes("text-grey-6")

