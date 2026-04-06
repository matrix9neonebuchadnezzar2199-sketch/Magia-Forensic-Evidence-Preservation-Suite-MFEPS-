"""
MFEPS v2.2.0 — エントリーポイント
1. 設定読込
2. フォルダ構造確保
3. ロギング初期化
4. DB 初期化・初回管理者
5. 管理者権限チェック
6. Storage（on_startup）
7. ページルーティング
8. NiceGUI 起動
"""
import asyncio
import ctypes
import os
import secrets
import sys
from pathlib import Path

# パス設定（src/ をインポートルートに追加）
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# NiceGUI のローカルファイルストレージ（既定はリポジトリ直下 .nicegui）。
# Cursor 等で別プロセスと同じパスを共有すると WinError 32 が発生しうるため、
# data 配下に隔離する。nicegui.storage の import より前に環境変数を設定すること。
_ng_storage_dir = (BASE_DIR / "data" / ".nicegui").resolve()
_ng_storage_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("NICEGUI_STORAGE_PATH", str(_ng_storage_dir))

from nicegui import ui, app

from src.utils.config import get_config
from src.utils.user_settings import apply_user_settings_to_environ, merge_file_into_storage
from src.utils.constants import APP_VERSION
from src.utils.folder_manager import ensure_project_structure
from src.utils.logger import setup_logging, get_logger
from src.models.database import init_database
from src.services.auth_service import ensure_default_admin
from src.services.remote_service import get_remote_service
from src.ui.layout import create_layout
from src.ui.pages.login import build_login_page
from src.ui.pages.dashboard import build_dashboard
from src.ui.pages.settings import build_settings
from src.ui.pages.usb_hdd import build_usb_hdd_page
from src.ui.pages.optical import build_optical_page
from src.ui.pages.reports import build_reports_page
from src.ui.pages.coc import build_coc_page
from src.ui.pages.audit import build_audit_page
from src.ui.pages.hash_verify import build_hash_verify_page
from src.ui.pages.admin_users import build_admin_users_page
from src.ui.pages.cases import build_cases_page


def is_admin() -> bool:
    """管理者権限で実行されているかチェック"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _get_or_create_storage_secret(data_dir: Path) -> str:
    """NiceGUI storage 署名用の秘密鍵（インスタンスごとに永続化）"""
    env_secret = (os.environ.get("MFEPS_STORAGE_SECRET") or "").strip()
    if env_secret:
        return env_secret
    secret_file = data_dir / ".storage_secret"
    if secret_file.exists():
        return secret_file.read_text(encoding="utf-8").strip()
    secret = secrets.token_hex(32)
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    secret_file.write_text(secret, encoding="utf-8")
    return secret


def main():
    """メインエントリーポイント"""
    # 1. ユーザー保存設定を環境へ（get_config より前）
    _data_dir = BASE_DIR / "data"
    apply_user_settings_to_environ(_data_dir)
    config = get_config()

    # libdvdcss は getenv するため、pydvdcss 初回ロード前に環境へ載せる
    _dv = (config.dvdcss_verbose or "").strip()
    if _dv:
        os.environ["DVDCSS_VERBOSE"] = _dv
    _dm = (config.dvdcss_method or "").strip()
    if _dm:
        os.environ["DVDCSS_METHOD"] = _dm

    # 2. フォルダ構造確保
    ensure_project_structure(config.base_dir)

    # 3. ロギング初期化
    setup_logging(config.logs_dir, config.mfeps_log_level)
    logger = get_logger("main")

    # Windows: pydvdcss / libaacs 等が ctypes で libs/*.dll を解決できるようにする
    if sys.platform == "win32":
        try:
            _libs = config.libs_dir.resolve()
            _libs.mkdir(parents=True, exist_ok=True)
            os.add_dll_directory(str(_libs))
            logger.debug("Windows: DLL 検索パスに追加 %s", _libs)
        except OSError as exc:
            logger.warning("Windows: os.add_dll_directory(libs) 失敗: %s", exc)

    logger.info("=" * 60)
    logger.info(f"MFEPS v{APP_VERSION} 起動開始")
    logger.info(f"ベースディレクトリ: {config.base_dir}")
    logger.info("=" * 60)

    # 4. DB初期化 + 初回管理者
    init_database(config.db_path)
    logger.info(f"データベース初期化完了: {config.db_path}")
    ensure_default_admin()
    get_remote_service()

    # 5. 管理者権限チェック
    admin = is_admin()
    if admin:
        logger.info("管理者権限: ✅ 確認済み")
    else:
        logger.warning("管理者権限: ⚠️ 未取得 — デバイスアクセスが制限されます")

    # 6. Storage 初期化を startup イベント内で実行
    _admin = admin

    def _proactor_exception_handler(loop, context):
        """ProactorEventLoop の ConnectionResetError を DEBUG に格下げ"""
        exc = context.get("exception")
        msg = str(context.get("message", ""))
        if isinstance(exc, ConnectionResetError) and (
            "ProactorBasePipeTransport" in msg
            or "ProactorBasePipeTransport" in str(exc)
        ):
            logger.debug(
                "ProactorEventLoop pipe transport closed: %s",
                msg or exc,
            )
            return
        loop.default_exception_handler(context)

    @app.on_startup
    async def on_startup():
        merge_file_into_storage(app.storage.general, config.data_dir)
        app.storage.general["status_text"] = "準備完了"
        app.storage.general["disk_free"] = ""
        app.storage.general["is_admin"] = _admin
        loop = asyncio.get_running_loop()
        app.storage.general["_nicegui_loop"] = loop
        from src.utils.i18n import get_i18n

        locale = app.storage.general.get("locale", "ja")
        get_i18n().set_locale(locale if locale in ("ja", "en") else "ja")
        if sys.platform == "win32":
            from src.core.device_watcher import get_device_watcher

            get_device_watcher().start()
        if hasattr(loop, "set_exception_handler"):
            loop.set_exception_handler(_proactor_exception_handler)

    # 7. ページルーティング
    @ui.page("/login")
    def page_login():
        build_login_page()

    @ui.page("/")
    def page_dashboard():
        create_layout("/", build_dashboard)

    @ui.page("/cases")
    def page_cases():
        create_layout("/cases", build_cases_page)

    @ui.page("/settings")
    def page_settings():
        create_layout("/settings", build_settings)

    @ui.page("/usb-hdd")
    def page_usb_hdd():
        create_layout("/usb-hdd", build_usb_hdd_page)

    @ui.page("/optical")
    def page_optical():
        create_layout("/optical", build_optical_page)

    @ui.page("/hash-verify")
    def page_hash_verify():
        create_layout("/hash-verify", build_hash_verify_page)

    @ui.page("/coc")
    def page_coc():
        create_layout("/coc", build_coc_page)

    @ui.page("/reports")
    def page_reports():
        create_layout("/reports", build_reports_page)

    @ui.page("/audit")
    def page_audit():
        create_layout("/audit", build_audit_page)

    @ui.page("/admin/users")
    def page_admin_users():
        create_layout("/admin/users", build_admin_users_page)

    # 法的免責ダイアログは各ページの layout 内で表示
    # (on_connect は NiceGUI 3.x では UI 要素の操作に制限あり)

    # 8. NiceGUI 起動
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
