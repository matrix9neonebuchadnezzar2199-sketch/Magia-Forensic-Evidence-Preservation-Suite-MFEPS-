"""
MFEPS v2.1.0 — 設定ダイアログ
フォントサイズ、バッファ、RFC3161、テーマ等の設定
"""
from pathlib import Path

from nicegui import ui, app

from src.core.e01_writer import E01Writer
from src.models.enums import AuditCategory
from src.utils.config import get_config, reload_config
from src.utils.constants import (
    BUFFER_SIZE_OPTIONS,
    COLOR_INFO,
    COLOR_SUCCESS,
    COLOR_WARNING,
    E01_COMPRESSION_OPTIONS,
    E01_FORMAT_OPTIONS,
    E01_SEGMENT_SIZE_OPTIONS_UI,
)


def build_settings():
    """設定画面を構築"""
    ui.label("⚙️ 設定").classes("text-h5 text-weight-bold q-mb-md")

    config = get_config()

    # ストレージから前回値を復元（なければデフォルト）
    stored = app.storage.general
    current_font = stored.get("font_size", config.mfeps_font_size)
    current_theme = stored.get("theme", config.mfeps_theme)
    current_buffer = stored.get("buffer_label", "1 MiB")
    current_error_action = stored.get("error_action", "ゼロ埋め+続行")
    current_output = stored.get("output_dir", str(config.mfeps_output_dir))
    current_rfc3161 = stored.get("rfc3161_enabled", config.mfeps_rfc3161_enabled)
    current_tsa = stored.get("tsa_url", config.mfeps_rfc3161_tsa_url)
    current_double_read = stored.get("double_read", config.mfeps_double_read_optical)

    # ==== アカウント管理 ====
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ アカウント管理").classes("text-subtitle1 text-weight-bold q-mb-sm")
        ui.separator()

        current_pw = ui.input(
            "現在のパスワード",
            password=True,
            password_toggle_button=True,
        ).classes("full-width")
        new_pw = ui.input(
            "新しいパスワード",
            password=True,
            password_toggle_button=True,
        ).classes("full-width q-mt-sm")
        confirm_pw = ui.input(
            "新しいパスワード（確認）",
            password=True,
            password_toggle_button=True,
        ).classes("full-width q-mt-sm")

        async def change_password():
            if not current_pw.value or not new_pw.value:
                ui.notify("全ての欄を入力してください", type="warning")
                return
            if new_pw.value != confirm_pw.value:
                ui.notify("新しいパスワードが一致しません", type="negative")
                return
            if len(new_pw.value) < 8:
                ui.notify("パスワードは8文字以上にしてください", type="warning")
                return

            from src.services.auth_service import get_auth_service
            from src.ui.session_auth import get_current_user_id
            from src.models.database import session_scope
            from src.models.schema import User
            from src.services.audit_service import get_audit_service

            auth = get_auth_service()
            user_id = get_current_user_id()
            if not user_id:
                ui.notify("ログインセッションが無効です", type="negative")
                return

            username_for_audit = ""
            try:
                with session_scope() as session:
                    user = session.query(User).filter(User.id == user_id).first()
                    if not user:
                        ui.notify("ユーザーが見つかりません", type="negative")
                        return
                    if not auth.verify_password(current_pw.value, user.password_hash):
                        ui.notify("現在のパスワードが正しくありません", type="negative")
                        return
                    username_for_audit = user.username
                    user.password_hash = auth.hash_password(new_pw.value)
            except Exception as e:
                ui.notify(f"パスワード変更に失敗しました: {e}", type="negative")
                return

            get_audit_service().add_entry(
                level="INFO",
                category=AuditCategory.AUTH.value,
                message=f"パスワード変更: {username_for_audit}",
                detail="",
            )

            current_pw.value = ""
            new_pw.value = ""
            confirm_pw.value = ""
            ui.notify("パスワードを変更しました", type="positive")

        ui.button(
            "パスワードを変更",
            on_click=change_password,
            icon="lock_reset",
            color="primary",
        ).classes("q-mt-md").props("unelevated")

    # ==== 表示設定 ====
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ 表示").classes("text-subtitle1 text-weight-bold q-mb-sm")

        with ui.row().classes("items-center gap-4 full-width"):
            ui.label("フォントサイズ:").classes("text-body2")
            font_slider = ui.slider(
                min=12, max=24, step=1, value=current_font
            ).classes("full-width").props("label-always")
            font_label = ui.label(f"{current_font}px").classes("text-body2 text-weight-bold")

        def on_font_change(e):
            try:
                size = int(e.args)
            except (TypeError, ValueError):
                try:
                    size = int(e.sender.value)
                except Exception:
                    return
            font_label.text = f"{size}px"
            css = (
                f"* {{ font-size: {size}px !important; }} "
                f".text-h5 {{ font-size: {int(size * 1.5)}px !important; }} "
                f".text-h6 {{ font-size: {int(size * 1.25)}px !important; }} "
                f".text-caption {{ font-size: {int(size * 0.75)}px !important; }}"
            )
            js = (
                'var style = document.getElementById("mfeps-font-override");'
                'if (!style) {'
                '  style = document.createElement("style");'
                '  style.id = "mfeps-font-override";'
                '  document.head.appendChild(style);'
                '}'
                'style.textContent = "' + css.replace('"', '\\"') + '";'
            )
            ui.run_javascript(js)




            stored["font_size"] = size

        font_slider.on("update:model-value", on_font_change)

        with ui.row().classes("items-center gap-4 q-mt-sm"):
            ui.label("テーマ:").classes("text-body2")
            ui.label("ダークモード").classes("text-body2 text-grey-5")
            ui.label("（ライトモードは将来バージョンで対応予定）").classes("text-caption text-grey-7")


    # ==== イメージング設定 ====
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ イメージング").classes("text-subtitle1 text-weight-bold q-mb-sm")

        with ui.row().classes("items-center gap-4"):
            ui.label("バッファサイズ:").classes("text-body2")
            buffer_select = ui.select(
                options=list(BUFFER_SIZE_OPTIONS.keys()),
                value=current_buffer,
                on_change=lambda e: stored.update({"buffer_label": e.sender.value})
            ).classes("min-w-32")

        with ui.row().classes("items-center gap-4 q-mt-sm"):
            ui.label("エラー時動作:").classes("text-body2")
            error_select = ui.select(
                options=["ゼロ埋め+続行", "スキップ+続行", "停止"],
                value=current_error_action,
                on_change=lambda e: stored.update({"error_action": e.sender.value})
            ).classes("min-w-32")

        with ui.row().classes("items-center gap-4 q-mt-sm"):
            ui.label("出力先デフォルト:").classes("text-body2")
            output_input = ui.input(
                value=current_output,
                on_change=lambda e: stored.update({"output_dir": e.sender.value})
            ).classes("flex-grow")

    # ==== ハッシュ設定 ====
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ ハッシュ").classes("text-subtitle1 text-weight-bold q-mb-sm")

        hash_md5 = stored.get("hash_md5", True)
        hash_sha1 = stored.get("hash_sha1", True)
        hash_sha256 = stored.get("hash_sha256", True)
        hash_sha512 = stored.get("hash_sha512", False)

        with ui.row().classes("items-center gap-4"):
            ui.checkbox("MD5", value=hash_md5,
                on_change=lambda e: stored.update({"hash_md5": e.sender.value}))
            ui.checkbox("SHA-1", value=hash_sha1,
                on_change=lambda e: stored.update({"hash_sha1": e.sender.value}))
            ui.checkbox("SHA-256", value=hash_sha256,
                on_change=lambda e: stored.update({"hash_sha256": e.sender.value}))
            ui.checkbox("SHA-512（処理時間増加）", value=hash_sha512,
                on_change=lambda e: stored.update({"hash_sha512": e.sender.value}))

    # ==== 検証オプション ====
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ 検証オプション").classes("text-subtitle1 text-weight-bold q-mb-sm")

        rfc3161_switch = ui.switch("RFC3161 タイムスタンプ取得", value=current_rfc3161,
            on_change=lambda e: stored.update({"rfc3161_enabled": e.sender.value}))
        with ui.row().classes("items-center gap-4 q-ml-lg q-mt-xs"):
            ui.label("TSA サーバー:").classes("text-body2")
            tsa_input = ui.input(
                value=current_tsa,
                on_change=lambda e: stored.update({"tsa_url": e.sender.value})
            ).classes("flex-grow")

        ui.switch("光学メディア 2回読取検証", value=current_double_read,
            on_change=lambda e: stored.update({"double_read": e.sender.value})).classes("q-mt-sm")

    # ==== E01 出力設定 ====
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ E01 出力 (ewfacquire)").classes(
            "text-subtitle1 text-weight-bold q-mb-sm"
        )
        ui.separator()

        current_ewfacquire = stored.get(
            "ewfacquire_path", config.ewfacquire_path
        )
        current_ewfverify = stored.get(
            "ewfverify_path", config.ewfverify_path
        )
        current_e01_compression = stored.get(
            "e01_compression",
            f"{config.e01_compression_method}:{config.e01_compression_level}",
        )
        seg_keys = list(E01_SEGMENT_SIZE_OPTIONS_UI.keys())
        current_e01_segment = stored.get(
            "e01_segment_size", str(config.e01_segment_size_bytes)
        )
        if str(current_e01_segment) not in seg_keys:
            current_e01_segment = "1500000000"
        else:
            current_e01_segment = str(current_e01_segment)

        fmt_keys = list(E01_FORMAT_OPTIONS.keys())
        current_e01_format = stored.get(
            "e01_ewf_format", config.e01_ewf_format
        )
        if current_e01_format not in fmt_keys:
            current_e01_format = "encase6"

        e01_status_container = ui.column().classes("full-width q-mb-md")

        def _render_e01_status(status: dict) -> None:
            e01_status_container.clear()
            with e01_status_container:
                avail = status.get("ewfacquire_available", False)
                verify_avail = status.get("ewfverify_available", False)

                if avail:
                    with ui.card().classes("q-pa-sm full-width").style(
                        f"border-left: 3px solid {COLOR_SUCCESS};"
                    ):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("check_circle", color="positive", size="sm")
                            ui.label("E01 出力: 利用可能").classes(
                                "text-weight-bold text-positive"
                            )
                        if status.get("ewfacquire_version"):
                            ui.label(
                                f"ewfacquire: {status['ewfacquire_version']}"
                            ).classes("text-caption text-grey-5 q-ml-lg")
                        if verify_avail:
                            ui.label(
                                f"ewfverify: {status.get('ewfverify_version', '')}"
                            ).classes("text-caption text-grey-5 q-ml-lg")
                        else:
                            ui.label(
                                "ewfverify: 未設定（取得後の自動検証をスキップします）"
                            ).classes("text-caption text-warning q-ml-lg")
                else:
                    with ui.card().classes("q-pa-sm full-width").style(
                        f"border-left: 3px solid {COLOR_WARNING};"
                    ):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("info", color="warning", size="sm")
                            ui.label("E01 出力: 未構成").classes(
                                "text-weight-bold text-warning"
                            )
                        ui.label(
                            "ewfacquire.exe のパスを設定すると、"
                            "USB/HDD イメージングで E01 形式を選択できるようになります。"
                        ).classes("text-caption text-grey-5 q-ml-lg")

                        for msg in status.get("diagnostics", []):
                            ui.label(f"• {msg}").classes(
                                "text-caption text-grey-6 q-ml-lg"
                            )

        initial_status = E01Writer.check_available_detail()
        _render_e01_status(initial_status)

        ui.label("ツールパス").classes(
            "text-subtitle2 text-weight-bold q-mt-md q-mb-xs"
        )

        with ui.row().classes("items-center gap-2 full-width"):
            ui.label("ewfacquire:").classes("text-body2 min-w-24")
            ewfacquire_input = ui.input(
                value=current_ewfacquire,
                placeholder="./libs/ewfacquire.exe",
                on_change=lambda e: stored.update(
                    {"ewfacquire_path": e.sender.value}
                ),
            ).classes("flex-grow").props("dense")

        with ui.row().classes("items-center gap-2 full-width q-mt-xs"):
            ui.label("ewfverify:").classes("text-body2 min-w-24")
            ewfverify_input = ui.input(
                value=current_ewfverify,
                placeholder="./libs/ewfverify.exe（任意）",
                on_change=lambda e: stored.update(
                    {"ewfverify_path": e.sender.value}
                ),
            ).classes("flex-grow").props("dense")

        async def _test_e01_connection() -> None:
            import subprocess as sp

            acq_path = (ewfacquire_input.value or "").strip()
            ver_path = (ewfverify_input.value or "").strip()

            test_result: dict = {
                "ewfacquire_available": False,
                "ewfverify_available": False,
                "ewfacquire_version": "",
                "ewfverify_version": "",
                "ewfacquire_status": "未設定",
                "ewfverify_status": "未設定",
                "diagnostics": [],
            }

            if acq_path:
                if not Path(acq_path).is_file():
                    test_result["ewfacquire_status"] = "ファイル未検出"
                    test_result["diagnostics"].append(
                        f"ファイルが存在しません: {acq_path}"
                    )
                else:
                    try:
                        proc = sp.run(
                            [acq_path, "-V"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                            creationflags=getattr(sp, "CREATE_NO_WINDOW", 0),
                        )
                        out = (proc.stdout or proc.stderr or "").strip()
                        if proc.returncode == 0 or out:
                            test_result["ewfacquire_available"] = True
                            test_result["ewfacquire_version"] = out
                            test_result["ewfacquire_status"] = "利用可能"
                        else:
                            test_result["ewfacquire_status"] = "実行エラー"
                            test_result["diagnostics"].append(
                                f"ewfacquire -V が異常終了 (code={proc.returncode})"
                            )
                    except sp.TimeoutExpired:
                        test_result["ewfacquire_status"] = "タイムアウト"
                        test_result["diagnostics"].append(
                            "ewfacquire -V がタイムアウトしました"
                        )
                    except Exception as ex:
                        test_result["ewfacquire_status"] = "例外"
                        test_result["diagnostics"].append(str(ex))
            else:
                test_result["diagnostics"].append("ewfacquire パスが空です")

            if ver_path:
                if not Path(ver_path).is_file():
                    test_result["ewfverify_status"] = "ファイル未検出"
                    test_result["diagnostics"].append(
                        f"ファイルが存在しません: {ver_path}"
                    )
                else:
                    try:
                        proc = sp.run(
                            [ver_path, "-V"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                            creationflags=getattr(sp, "CREATE_NO_WINDOW", 0),
                        )
                        out = (proc.stdout or proc.stderr or "").strip()
                        if proc.returncode == 0 or out:
                            test_result["ewfverify_available"] = True
                            test_result["ewfverify_version"] = out
                            test_result["ewfverify_status"] = "利用可能"
                        else:
                            test_result["ewfverify_status"] = "実行エラー"
                    except Exception:
                        test_result["ewfverify_status"] = "例外"
            else:
                test_result["ewfverify_status"] = "未設定（検証スキップ）"

            _render_e01_status(test_result)

            if test_result["ewfacquire_available"]:
                ui.notify(
                    f"✅ ewfacquire 接続成功: "
                    f"{test_result['ewfacquire_version']}",
                    type="positive",
                )
            else:
                ui.notify(
                    f"❌ ewfacquire 接続失敗: "
                    f"{test_result['ewfacquire_status']}",
                    type="negative",
                )

        ui.button(
            "🔍 接続テスト",
            on_click=_test_e01_connection,
            icon="play_circle",
        ).props("outline dense").classes("q-mt-sm")

        ui.separator().classes("q-my-md")

        ui.label("デフォルト取得設定").classes(
            "text-subtitle2 text-weight-bold q-mb-xs"
        )
        ui.label(
            "USB/HDD イメージング画面で E01 選択時のデフォルト値です。"
            "個別のジョブで上書きできます。"
        ).classes("text-caption text-grey-6 q-mb-sm")

        with ui.row().classes("items-center gap-4"):
            ui.label("圧縮:").classes("text-body2 min-w-32")
            ui.select(
                options=E01_COMPRESSION_OPTIONS,
                value=current_e01_compression,
                on_change=lambda e: stored.update(
                    {"e01_compression": e.sender.value}
                ),
            ).classes("min-w-64")

        with ui.row().classes("items-center gap-4 q-mt-sm"):
            ui.label("セグメントサイズ:").classes("text-body2 min-w-32")
            ui.select(
                options=E01_SEGMENT_SIZE_OPTIONS_UI,
                value=current_e01_segment,
                on_change=lambda e: stored.update(
                    {"e01_segment_size": e.sender.value}
                ),
            ).classes("min-w-64")

        with ui.row().classes("items-center gap-4 q-mt-sm"):
            ui.label("EWF フォーマット:").classes("text-body2 min-w-32")
            ui.select(
                options=E01_FORMAT_OPTIONS,
                value=current_e01_format,
                on_change=lambda e: stored.update(
                    {"e01_ewf_format": e.sender.value}
                ),
            ).classes("min-w-64")

        with ui.card().classes("q-pa-xs q-mt-sm full-width").style(
            f"border-left: 3px solid {COLOR_INFO}; background: rgba(68,138,255,0.05);"
        ):
            ui.label(
                "💡 encase5 以前は最大セグメントサイズが 1.9 GiB に制限されます。"
                "2 GiB 以上のセグメントには encase6 以降を選択してください。"
            ).classes("text-caption text-grey-5")

        ui.separator().classes("q-my-md")

        ui.label("ライセンス").classes(
            "text-subtitle2 text-weight-bold q-mb-xs"
        )
        with ui.row().classes("items-center gap-2"):
            ui.icon("gavel", size="xs").classes("text-grey-6")
            ui.label(
                "libewf (ewfacquire / ewfverify) は LGPL-3.0+ です。"
                "MFEPS はバイナリを同梱せず、ユーザーが配置する方式のため "
                "MIT ライセンスとの競合はありません。"
            ).classes("text-caption text-grey-6")

        with ui.row().classes("items-center gap-2 q-mt-xs flex-wrap"):
            ui.icon("open_in_new", size="xs").classes("text-grey-6")
            ui.link(
                "libewf GitHub",
                "https://github.com/libyal/libewf",
                new_tab=True,
            ).classes("text-caption")
            ui.label("|").classes("text-caption text-grey-7")
            ui.link(
                "ビルド手順 (Wiki)",
                "https://github.com/libyal/libewf/wiki/Building",
                new_tab=True,
            ).classes("text-caption")
            ui.label("|").classes("text-caption text-grey-7")
            ui.label("ローカル: libs/README_ewftools.md").classes(
                "text-caption text-grey-6"
            )

    # ==== 映像圧縮設定 ====
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ 映像圧縮").classes("text-subtitle1 text-weight-bold q-mb-sm")

        with ui.row().classes("items-center gap-4"):
            ui.label("ffmpeg パス:").classes("text-body2")
            ui.input(
                value=stored.get("ffmpeg_path", "./libs/ffmpeg.exe"),
                on_change=lambda e: stored.update({"ffmpeg_path": e.sender.value})
            ).classes("flex-grow")

        with ui.row().classes("items-center gap-4 q-mt-sm"):
            ui.label("デフォルト目標サイズ:").classes("text-body2")
            ui.select(
                options=["4.7 GB (DVD-5)", "8.5 GB (DVD-9)", "25 GB (BD-25)"],
                value=stored.get("target_size", "4.7 GB (DVD-5)"),
                on_change=lambda e: stored.update({"target_size": e.sender.value})
            )

    # ==== データベース管理 ====
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ データベース").classes("text-subtitle1 text-weight-bold q-mb-sm")

        with ui.row().classes("items-center gap-4"):
            ui.label("DB ファイル:").classes("text-body2")
            ui.input(value=str(config.db_path)).props("readonly").classes("flex-grow")

        async def on_reset_db():
            with ui.dialog() as confirm_dialog, ui.card():
                ui.label("⚠️ 本当にデータベースを初期化しますか？").classes("text-h6")
                ui.label("全データが削除されます。この操作は取り消せません。").classes(
                    "text-body2 text-grey-5")
                with ui.row().classes("justify-end q-mt-md"):
                    ui.button("キャンセル", on_click=confirm_dialog.close).props("flat")

                    async def do_reset():
                        from src.models.database import init_database
                        import os
                        db_path = config.db_path
                        if db_path.exists():
                            os.remove(db_path)
                        init_database(db_path)
                        confirm_dialog.close()
                        ui.notify("✅ データベースを初期化しました", type="positive")

                    ui.button("初期化", on_click=do_reset, color="negative")
            confirm_dialog.open()

        ui.button(
            "🗑️ DB 初期化", on_click=on_reset_db, color="negative"
        ).props("outline").classes("q-mt-sm")

    # ==== 保存・リセット ====
    with ui.row().classes("justify-end q-mt-md gap-2"):
        def on_reset_settings():
            stored["font_size"] = 16
            stored["theme"] = "dark"
            stored["buffer_label"] = "1 MiB"
            stored["error_action"] = "ゼロ埋め+続行"
            stored["output_dir"] = "./output"
            stored["rfc3161_enabled"] = False
            stored["tsa_url"] = "http://timestamp.digicert.com"
            stored["double_read"] = False
            stored["hash_md5"] = True
            stored["hash_sha1"] = True
            stored["hash_sha256"] = True
            stored["hash_sha512"] = False
            stored["ewfacquire_path"] = ""
            stored["ewfverify_path"] = ""
            stored["e01_compression"] = "deflate:fast"
            stored["e01_segment_size"] = "1500000000"
            stored["e01_ewf_format"] = "encase6"
            ui.dark_mode(True)
            ui.run_javascript('document.body.style.fontSize = "16px"')
            ui.notify("設定をリセットしました。ページをリロードしてください。", type="info")

        ui.button("リセット", icon="restart_alt", on_click=on_reset_settings).props("flat")

        def on_save_settings():
            ui.notify("✅ 設定を保存しました", type="positive")

        ui.button("保存", icon="save", color="primary", on_click=on_save_settings).props("unelevated")
