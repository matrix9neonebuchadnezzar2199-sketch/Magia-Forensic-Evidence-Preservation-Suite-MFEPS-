"""
MFEPS v2.0 — 設定ダイアログ
フォントサイズ、バッファ、RFC3161、テーマ等の設定
"""
from nicegui import ui, app
from src.utils.constants import BUFFER_SIZE_OPTIONS


def build_settings():
    """設定画面を構築"""
    ui.label("⚙️ 設定").classes("text-h5 text-weight-bold q-mb-md")

    # ---- 表示設定 ----
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ 表示").classes("text-subtitle1 text-weight-bold q-mb-sm")

        # フォントサイズ
        with ui.row().classes("items-center gap-4 full-width"):
            ui.label("フォントサイズ:").classes("text-body2")
            font_slider = ui.slider(
                min=12, max=24, step=1, value=16
            ).classes("full-width").props("label-always")
            font_label = ui.label("16px").classes("text-body2")

        def on_font_change(e):
            size = int(e.value)
            font_label.text = f"{size}px"
            ui.query("body").style(f"font-size: {size}px")
            app.storage.user["font_size"] = size

        font_slider.on("update:model-value", on_font_change)

        # ダークモード
        with ui.row().classes("items-center gap-4 q-mt-sm"):
            ui.label("テーマ:").classes("text-body2")
            dark_toggle = ui.toggle(
                ["ダーク", "ライト"], value="ダーク"
            ).props("dense")

        def on_theme_change(e):
            is_dark = e.value == "ダーク"
            ui.dark_mode(is_dark)
            app.storage.user["theme"] = "dark" if is_dark else "light"

        dark_toggle.on("update:model-value", on_theme_change)

    # ---- イメージング設定 ----
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ イメージング").classes("text-subtitle1 text-weight-bold q-mb-sm")

        with ui.row().classes("items-center gap-4"):
            ui.label("バッファサイズ:").classes("text-body2")
            buffer_select = ui.select(
                options=list(BUFFER_SIZE_OPTIONS.keys()),
                value="1 MiB",
            ).classes("min-w-32")

        with ui.row().classes("items-center gap-4 q-mt-sm"):
            ui.label("エラー時動作:").classes("text-body2")
            ui.select(
                options=["ゼロ埋め+続行", "スキップ+続行", "停止"],
                value="ゼロ埋め+続行",
            ).classes("min-w-32")

        with ui.row().classes("items-center gap-4 q-mt-sm"):
            ui.label("出力先デフォルト:").classes("text-body2")
            output_input = ui.input(value="./output").classes("flex-grow")

    # ---- ハッシュ設定 ----
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ ハッシュ").classes("text-subtitle1 text-weight-bold q-mb-sm")

        with ui.row().classes("items-center gap-4"):
            ui.checkbox("MD5", value=True)
            ui.checkbox("SHA-1", value=True)
            ui.checkbox("SHA-256", value=True)
            ui.checkbox("SHA-512（処理時間増加）", value=False)

    # ---- 検証オプション ----
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ 検証オプション").classes("text-subtitle1 text-weight-bold q-mb-sm")

        rfc3161_switch = ui.switch("RFC3161 タイムスタンプ取得", value=False)
        with ui.row().classes("items-center gap-4 q-ml-lg q-mt-xs"):
            ui.label("TSA サーバー:").classes("text-body2")
            tsa_input = ui.input(
                value="http://timestamp.digicert.com"
            ).classes("flex-grow")

        ui.switch("光学メディア 2回読取検証", value=False).classes("q-mt-sm")

    # ---- 映像圧縮設定 ----
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ 映像圧縮").classes("text-subtitle1 text-weight-bold q-mb-sm")

        with ui.row().classes("items-center gap-4"):
            ui.label("ffmpeg パス:").classes("text-body2")
            ui.input(value="./libs/ffmpeg.exe").classes("flex-grow")

        with ui.row().classes("items-center gap-4 q-mt-sm"):
            ui.label("デフォルト目標サイズ:").classes("text-body2")
            ui.select(
                options=["4.7 GB (DVD-5)", "8.5 GB (DVD-9)", "25 GB (BD-25)"],
                value="4.7 GB (DVD-5)",
            )

    # ---- データベース管理 ----
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ データベース").classes("text-subtitle1 text-weight-bold q-mb-sm")

        with ui.row().classes("items-center gap-4"):
            ui.label("DB ファイル:").classes("text-body2")
            ui.input(value="./data/mfeps.db", readonly=True).classes("flex-grow")

        async def on_reset_db():
            with ui.dialog() as confirm_dialog, ui.card():
                ui.label("⚠️ 本当にデータベースを初期化しますか？").classes("text-h6")
                ui.label("全データが削除されます。この操作は取り消せません。").classes(
                    "text-body2 text-grey-5")
                with ui.row().classes("justify-end q-mt-md"):
                    ui.button("キャンセル", on_click=confirm_dialog.close).props("flat")
                    ui.button("初期化", on_click=confirm_dialog.close, color="negative")
            confirm_dialog.open()

        ui.button(
            "🗑️ DB 初期化", on_click=on_reset_db, color="negative"
        ).props("outline").classes("q-mt-sm")

    # ---- 保存ボタン ----
    with ui.row().classes("justify-end q-mt-md gap-2"):
        ui.button("リセット", icon="restart_alt").props("flat")
        ui.button("保存", icon="save", color="primary").props("unelevated")
