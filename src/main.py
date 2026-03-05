"""
MFEPS v2.0 — エントリーポイント
1. フォルダ構造確保
2. 設定読込
3. DB初期化
4. 管理者権限チェック
5. NiceGUI起動
"""
import sys
import ctypes
import logging
from pathlib import Path

# パス設定（src/ をインポートルートに追加）
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from nicegui import ui, app

from src.utils.config import get_config
from src.utils.folder_manager import ensure_project_structure
from src.utils.logger import setup_logging, get_logger
from src.models.database import init_database
from src.ui.theme.modern_dark import CUSTOM_CSS, QUASAR_BRAND_COLORS
from src.ui.layout import create_layout
from src.ui.pages.dashboard import build_dashboard
from src.ui.pages.settings import build_settings
from src.ui.pages.usb_hdd import build_usb_hdd_page
from src.ui.pages.optical import build_optical_page
from src.ui.pages.reports import build_reports_page
from src.ui.pages.coc import build_coc_page
from src.ui.pages.audit import build_audit_page


def is_admin() -> bool:
    """管理者権限で実行されているかチェック"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def main():
    """メインエントリーポイント"""
    # 1. 設定読込
    config = get_config()

    # 2. フォルダ構造確保
    ensure_project_structure(config.base_dir)

    # 3. ロギング初期化
    setup_logging(config.logs_dir, config.mfeps_log_level)
    logger = get_logger("main")
    logger.info("=" * 60)
    logger.info(f"MFEPS v2.0 起動開始")
    logger.info(f"ベースディレクトリ: {config.base_dir}")
    logger.info("=" * 60)

    # 4. DB初期化
    init_database(config.db_path)
    logger.info(f"データベース初期化完了: {config.db_path}")

    # 5. 管理者権限チェック
    admin = is_admin()
    if admin:
        logger.info("管理者権限: ✅ 確認済み")
    else:
        logger.warning("管理者権限: ⚠️ 未取得 — デバイスアクセスが制限されます")

    # 6. カスタムCSS注入
    ui.add_head_html(f"<style>{CUSTOM_CSS}</style>")

    # 7. Storage初期化
    app.storage.general["status_text"] = "準備完了"
    app.storage.general["disk_free"] = ""
    app.storage.general["is_admin"] = admin

    # 8. ページルーティング
    @ui.page("/")
    def page_dashboard():
        create_layout(build_dashboard)

    @ui.page("/settings")
    def page_settings():
        create_layout(build_settings)

    @ui.page("/usb-hdd")
    def page_usb_hdd():
        create_layout(build_usb_hdd_page)

    @ui.page("/optical")
    def page_optical():
        create_layout(build_optical_page)

    @ui.page("/hash-verify")
    def page_hash_verify():
        def content():
            ui.label("🔑 ハッシュ検証").classes("text-h5 text-weight-bold q-mb-md")
            ui.label("イメージングジョブからハッシュ検証を実行できます").classes("text-grey-6")
        create_layout(content)

    @ui.page("/coc")
    def page_coc():
        create_layout(build_coc_page)

    @ui.page("/reports")
    def page_reports():
        create_layout(build_reports_page)

    @ui.page("/audit")
    def page_audit():
        create_layout(build_audit_page)

    # 9. 起動時法的免責ダイアログ（初回起動時）
    @app.on_connect
    async def on_connect():
        if not app.storage.user.get("disclaimer_accepted"):
            with ui.dialog() as dialog, ui.card().classes("q-pa-lg"):
                ui.label("⚖️ 法的免責事項").classes("text-h5 text-weight-bold")
                ui.separator()
                ui.label(
                    "本ツールはデジタルフォレンジックの証拠保全を目的として設計されています。\n"
                    "コピーガード解除機能は、正当な法的権限に基づく証拠保全目的でのみ使用可能です。\n"
                    "不正競争防止法および著作権法に違反する使用は固く禁じます。\n"
                    "ユーザーは本ツールの使用に関する全ての責任を負います。"
                ).classes("text-body1").style("white-space: pre-line;")
                ui.separator()

                async def on_accept():
                    app.storage.user["disclaimer_accepted"] = True
                    dialog.close()

                with ui.row().classes("justify-end q-mt-md"):
                    ui.button("同意して続行", on_click=on_accept, color="primary").props("unelevated")

            dialog.open()

    # 10. NiceGUI起動
    logger.info(f"WebUI をポート {config.mfeps_port} で起動します...")
    ui.run(
        port=config.mfeps_port,
        title="MFEPS — Forensic Evidence Preservation Suite",
        favicon="🔬",
        dark=True,
        reload=False,
        show=True,
        storage_secret="mfeps-v2-secret-key",
    )


if __name__ == "__main__":
    main()
