"""
MFEPS v2.0 — エントリーポイント
1. フォルダ構造確保
2. 設定読込
3. DB初期化
4. 管理者権限チェック
5. NiceGUI起動
"""
import ctypes
import logging
import secrets
import sys
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
from src.services.auth_service import ensure_default_admin
from src.ui.theme.modern_dark import CUSTOM_CSS, QUASAR_BRAND_COLORS
from src.ui.layout import create_layout
from src.ui.pages.login import build_login_page
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


def _get_or_create_storage_secret(data_dir: Path) -> str:
    """NiceGUI storage 署名用の秘密鍵（インスタンスごとに永続化）"""
    secret_file = data_dir / ".storage_secret"
    if secret_file.exists():
        return secret_file.read_text(encoding="utf-8").strip()
    secret = secrets.token_hex(32)
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    secret_file.write_text(secret, encoding="utf-8")
    return secret


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

    # 4. DB初期化 + 初回管理者
    init_database(config.db_path)
    logger.info(f"データベース初期化完了: {config.db_path}")
    ensure_default_admin()

    # 5. 管理者権限チェック
    admin = is_admin()
    if admin:
        logger.info("管理者権限: ✅ 確認済み")
    else:
        logger.warning("管理者権限: ⚠️ 未取得 — デバイスアクセスが制限されます")

    # 7. Storage 初期化を startup イベント内で実行
    _admin = admin

    @app.on_startup
    async def on_startup():
        app.storage.general["status_text"] = "準備完了"
        app.storage.general["disk_free"] = ""
        app.storage.general["is_admin"] = _admin

    # 8. ページルーティング
    @ui.page("/login")
    def page_login():
        build_login_page()

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

    # 9. 法的免責ダイアログは各ページの layout 内で表示
    # (on_connect は NiceGUI 3.x では UI 要素の操作に制限あり)

    # 10. NiceGUI 起動
    logger.info(
        f"WebUI を {config.bind_address}:{config.mfeps_port} で起動します..."
    )
    ui.run(
        host=config.bind_address,
        port=config.mfeps_port,
        title="MFEPS — Forensic Evidence Preservation Suite",
        favicon="🔬",
        dark=True,
        reload=False,
        show=False,
        storage_secret=_get_or_create_storage_secret(config.data_dir),
    )


if __name__ == "__main__":
    main()
