"""
MFEPS v2.0 — 光学メディア (CD/DVD/BD) ウィザードページ
4段階ウィザード + コピーガード解析結果表示
"""
from nicegui import ui
import asyncio

from src.core.device_detector import detect_optical_drives, OpticalDriveInfo
from src.core.optical_engine import OpticalMediaAnalyzer
from src.core.copy_guard_analyzer import CopyGuardAnalyzer, ProtectionInfo
from src.ui.layout import create_layout


def build_optical_page():
    """光学メディアウィザード"""
    ui.label("💿 CD・DVD・BD イメージング").classes("text-h5 text-weight-bold q-mb-md")

    state = {"selected_drive": None, "analysis": None, "guard_result": None}

    with ui.stepper().classes("full-width").props("vertical animated") as stepper:

        # ===== STEP 1: ドライブ選択 =====
        with ui.step("ドライブ選択", icon="album"):
            ui.label("光学ドライブを選択してください").classes("text-body2 text-grey-5 q-mb-md")

            drive_container = ui.column().classes("full-width gap-2")
            status_label = ui.label("").classes("text-caption text-grey-6")

            async def refresh_drives():
                drive_container.clear()
                status_label.text = "🔍 ドライブ検出中..."
                drives = await asyncio.get_event_loop().run_in_executor(
                    None, detect_optical_drives)
                status_label.text = f"✅ {len(drives)} 台のドライブが検出されました"

                with drive_container:
                    for drv in drives:
                        _render_drive_option(drv, state)

            ui.button("🔄 ドライブ検出", on_click=refresh_drives, color="primary").props("unelevated")

            with ui.stepper_navigation():
                ui.button("次へ →", on_click=stepper.next, color="primary").props("unelevated")

        # ===== STEP 2: プリスキャン + コピーガード解析 =====
        with ui.step("プリスキャン・コピーガード解析", icon="search"):
            scan_container = ui.column().classes("full-width")

            with ui.card().classes("q-pa-md full-width q-mt-md"):
                ui.label("コピー設定").classes("text-subtitle2 text-weight-bold q-mb-sm")

                with ui.row().classes("gap-4 items-center"):
                    ui.label("案件番号:").classes("text-body2")
                    ui.input(placeholder="CASE-001").classes("min-w-48")

                with ui.row().classes("gap-4 items-center q-mt-sm"):
                    ui.label("証拠品番号:").classes("text-body2")
                    ui.input(placeholder="EV-001").classes("min-w-48")

                with ui.row().classes("gap-4 items-center q-mt-sm"):
                    ui.label("出力形式:").classes("text-body2")
                    ui.select(options=["ISO", "RAW (dd)"], value="ISO")

                ui.switch("二回読取検証（高信頼性）", value=False).classes("q-mt-sm")

            with ui.stepper_navigation():
                ui.button("← 戻る", on_click=stepper.previous).props("flat")
                ui.button("▶️ コピー開始 →", on_click=stepper.next,
                         color="primary").props("unelevated")

        # ===== STEP 3: コピー実行 =====
        with ui.step("コピー実行", icon="content_copy"):
            ui.label("⚙️ コピー実行中").classes("text-h6 q-mb-md")
            ui.linear_progress(value=0, show_value=True).classes("full-width")
            with ui.row().classes("gap-4 q-mt-sm"):
                ui.label("トラック: --").classes("text-body2")
                ui.label("速度: -- MiB/s").classes("text-body2")
                ui.label("リトライ: 0").classes("text-body2")
            ui.log(max_lines=100).classes("full-width q-mt-md").style("height: 200px;")

            with ui.row().classes("gap-2 q-mt-md"):
                ui.button("⏸ 一時停止").props("outline")
                ui.button("⏹ 中止", color="negative").props("outline")

            with ui.stepper_navigation():
                ui.button("結果を確認 →", on_click=stepper.next, color="primary").props("unelevated")

        # ===== STEP 4: リザルト =====
        with ui.step("リザルト", icon="check_circle"):
            ui.label("✅ コピー完了").classes("text-h6 q-mb-md")
            ui.label("結果はコピー実行後に表示されます").classes("text-caption text-grey-6")

            with ui.row().classes("gap-2 q-mt-lg"):
                ui.button("📄 報告書PDF", color="primary").props("unelevated")
                ui.button("📋 CoC追加").props("outline")
                ui.button("🏠 ダッシュボード",
                         on_click=lambda: ui.navigate.to("/")).props("outline")


def _render_drive_option(drive: OpticalDriveInfo, state: dict):
    """光学ドライブ選択オプション"""
    media_color = "positive" if drive.media_loaded else "grey"

    with ui.card().classes("q-pa-sm cursor-pointer full-width").style(
            "border-left: 3px solid rgba(108, 99, 255, 0.3);"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("album")
            ui.label(f"{drive.drive_letter}").classes("text-weight-bold")
            ui.label(drive.drive_model).classes("text-caption text-grey-5")

        with ui.row().classes("q-ml-lg items-center gap-1"):
            if drive.media_loaded:
                ui.icon("check_circle", size="xs", color="positive")
                ui.label("メディア装填済み").classes("text-caption text-positive")
            else:
                ui.icon("eject", size="xs", color="grey")
                ui.label("メディア未挿入").classes("text-caption text-grey-6")


def render_copy_guard_badges(protections: list[ProtectionInfo]):
    """コピーガード検出結果をバッジ表示"""
    with ui.card().classes("q-pa-md full-width"):
        ui.label("🔒 コピーガード解析結果").classes("text-subtitle2 text-weight-bold q-mb-sm")

        for prot in protections:
            if prot.detected:
                color = "positive" if prot.can_decrypt else "negative"
                icon = "check_circle" if prot.can_decrypt else "cancel"
            else:
                color = "grey"
                icon = "radio_button_unchecked"

            with ui.row().classes("items-center gap-2 q-mb-xs"):
                status = "🔴" if prot.detected and not prot.can_decrypt else (
                    "🟡" if prot.detected else "🟢")
                ui.label(status)
                ui.label(prot.type.upper()).classes("text-weight-bold text-body2")
                ui.label(prot.details).classes("text-caption text-grey-5")
