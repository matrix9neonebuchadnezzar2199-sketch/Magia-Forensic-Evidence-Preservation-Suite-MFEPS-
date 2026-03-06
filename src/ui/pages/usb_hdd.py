"""
MFEPS v2.0 — USB/HDD ウィザードページ
4段階ウィザード: ドライブ選択 → プリスキャン → コピー実行 → リザルト
"""
from nicegui import ui, app
import asyncio
import uuid
from src.core.device_detector import detect_block_devices, DeviceInfo, format_capacity
from src.core.write_blocker import check_write_protection, get_protection_badge
from src.ui.components.progress_panel import (
    render_progress_panel, render_hash_comparison, render_error_panel, render_hash_display
)
from src.ui.layout import create_layout
from src.services.imaging_service import get_imaging_service


def build_usb_hdd_page():
    """USB/HDDイメージング ウィザード"""
    ui.label("💾 USB・HDD イメージング").classes("text-h5 text-weight-bold q-mb-md")

    # 状態管理
    state = {
        "selected_device": None,
        "case_number": "",
        "evidence_number": "",
        "job_id": None,
        "result": None,
    }

    with ui.stepper().classes("full-width").props("vertical animated") as stepper:

        # ===== STEP 1: ドライブ選択 =====
        with ui.step("ドライブ選択", icon="usb"):
            ui.label("接続中のデバイスから対象を選択してください").classes("text-body2 text-grey-5 q-mb-md")

            device_container = ui.column().classes("full-width gap-2")
            status_label = ui.label("").classes("text-caption text-grey-6")

            async def refresh_devices():
                device_container.clear()
                status_label.text = "🔍 デバイス検出中..."

                devices = await asyncio.get_event_loop().run_in_executor(
                    None, detect_block_devices)

                status_label.text = f"✅ {len(devices)} 台のデバイスが検出されました"

                with device_container:
                    for dev in devices:
                        _render_device_option(dev, state, stepper)

            ui.button("🔄 デバイス検出", on_click=refresh_devices, color="primary").props("unelevated")

            with ui.stepper_navigation():
                ui.button("次へ →", on_click=lambda: stepper.next(), color="primary").props(
                    "unelevated").bind_enabled_from(state, "selected_device",
                    backward=lambda v: v is not None)

        # ===== STEP 2: プリスキャン・設定 =====
        with ui.step("プリスキャン・設定", icon="search"):
            ui.label("デバイス情報を確認し、コピー設定を行ってください").classes(
                "text-body2 text-grey-5 q-mb-md")

            scan_info = ui.column().classes("full-width")

            # 設定パネル
            with ui.card().classes("q-pa-md full-width q-mt-md"):
                ui.label("コピー設定").classes("text-subtitle2 text-weight-bold q-mb-sm")

                with ui.row().classes("gap-4 items-center"):
                    ui.label("案件番号:").classes("text-body2")
                    case_input = ui.input(placeholder="CASE-001").classes("min-w-48")

                with ui.row().classes("gap-4 items-center q-mt-sm"):
                    ui.label("証拠品番号:").classes("text-body2")
                    ev_input = ui.input(placeholder="EV-001").classes("min-w-48")

                verify_checkbox = ui.checkbox("コピー後にハッシュ検証を実行", value=True).classes("q-mt-sm")

            with ui.stepper_navigation():
                ui.button("← 戻る", on_click=stepper.previous).props("flat")
                
                async def start_copy():
                    if not state["selected_device"]:
                        ui.notify("デバイスが選択されていません", type="negative")
                        return

                    case_val = case_input.value
                    ev_val = ev_input.value

                    if not case_val or not ev_val:
                        ui.notify("案件番号と証拠品番号を入力してください", type="warning")
                        return

                    service = get_imaging_service()
                    job_id = await service.start_imaging(
                        device=state["selected_device"],
                        case_id=case_val,
                        evidence_id=ev_val,
                        verify=verify_checkbox.value,
                    )
                    state["job_id"] = job_id

                    # STEP 3 の初期化
                    progress_container.clear()
                    log_area.clear()
                    log_area.push(f"[{job_id}] イメージングジョブを開始しました...")

                    # ★ タイマーを有効化（生成はページ構築時に済み）
                    progress_timer.active = True

                    stepper.next()


                ui.button("▶️ コピー開始 →", on_click=start_copy,
                         color="primary").props("unelevated")

        # ===== STEP 3: コピー実行 =====
        with ui.step("コピー実行", icon="content_copy"):
            ui.label("⚙️ コピー実行中").classes("text-h6 q-mb-md")

            progress_container = ui.column().classes("full-width")
            log_area = ui.log(max_lines=100).classes("full-width q-mt-md").style("height: 200px;")

            async def cancel_job():
                if state.get("job_id"):
                    await get_imaging_service().cancel_imaging(state["job_id"])
                    log_area.push("⚠️ ジョブをキャンセルしました")
                    ui.notify("コピーを中止しました", type="warning")

            with ui.row().classes("gap-2 q-mt-md"):
                ui.button("⏸ 一時停止", icon="pause").props("outline")
                ui.button("⏹ 中止", on_click=cancel_job, icon="stop", color="negative").props("outline")

            with ui.stepper_navigation():
                btn_next = ui.button("結果を確認 →", on_click=stepper.next,
                         color="primary").props("unelevated")
                btn_next.disable()

            # ★ update_progress をここで定義（ページ構築スコープ内）
            def update_progress():
                if not state.get("job_id"):
                    return

                try:
                    service = get_imaging_service()
                    progress = service.get_progress(state["job_id"])
                    status = progress.get("status", "unknown")

                    progress_container.clear()
                    with progress_container:
                        render_progress_panel(progress)

                    if status in ["completed", "failed", "cancelled"]:
                        progress_timer.active = False  # ★ 変更
                        state["result"] = progress
                        btn_next.enable()

                        if status == "completed":
                            log_area.push("✅ イメージングが正常に完了しました")
                            ui.notify("コピーが完了しました！ 「結果を確認」ボタンを押してください。", type="positive")
                        elif status == "failed":
                            log_area.push(f"❌ イメージング失敗: {progress.get('error_message', '不明')}")
                            ui.notify("コピーが失敗しました", type="negative")
                        else:
                            log_area.push("⚠️ キャンセルされました")
                            ui.notify("コピーをキャンセルしました", type="warning")

                except Exception as ex:
                    import traceback
                    print(f"[UPDATE_PROGRESS ERROR] {ex}")
                    traceback.print_exc()
                    log_area.push(f"[ERROR] 進捗更新エラー: {ex}")

            # ★ タイマーをページ構築スコープで登録（初期状態OFF）
            progress_timer = ui.timer(1.0, update_progress, active=False)



        # ===== STEP 4: リザルト =====
        with ui.step("リザルト", icon="check_circle"):
            ui.label("✅ コピー完了").classes("text-h6 q-mb-md")

            result_container = ui.column().classes("full-width")

            def build_result_page():
                result_container.clear()
                res = state.get("result", {})
                
                with result_container:
                    if res.get("status") == "completed":
                        ui.label("イメージングプロセスの結果レポート").classes("text-body1 q-mb-md")
                        
                        # ハッシュ比較
                        src_hashes = res.get("source_hashes", {})
                        ver_hashes = res.get("verify_hashes", {})
                        if src_hashes and ver_hashes:
                            render_hash_comparison(src_hashes, ver_hashes, res.get("match_result", "failed"))
                        elif src_hashes:
                            render_hash_display(src_hashes, "ソースハッシュ (検証スキップ)")
                            
                        # エラーセクタ
                        if res.get("error_count", 0) > 0:
                            # 実際のエラーリストを渡す
                            render_error_panel([]) 
                    else:
                        ui.label(f"ジョブが正常に完了しませんでした ({res.get('status', 'unknown')})").classes("text-body1 text-negative")

            ui.label("結果はイメージングジョブ実行後に表示されます").classes(
                "text-caption text-grey-6")

            with ui.row().classes("gap-2 q-mt-lg"):
                ui.button("📄 報告書PDF", icon="picture_as_pdf", color="primary").props(
                    "unelevated")
                ui.button("📋 CoC追加", icon="link").props("outline")
                ui.button("🏠 ダッシュボード", icon="dashboard",
                         on_click=lambda: ui.navigate.to("/")).props("outline")


def _render_device_option(dev: DeviceInfo, state: dict, stepper):
    """デバイス選択オプションを表示"""
    is_system = dev.is_system_drive
    border_color = "#FF5252" if is_system else "rgba(108, 99, 255, 0.3)"

    with ui.card().classes("q-pa-sm cursor-pointer full-width").style(
            f"border-left: 3px solid {border_color};"):

        with ui.row().classes("items-center gap-2"):
            if not is_system:
                radio = ui.radio(
                    options=[dev.device_path],
                    on_change=lambda e, d=dev: state.update({"selected_device": d})
                )
            icon = "usb" if "USB" in dev.interface_type.upper() else "storage"
            ui.icon(icon)
            ui.label(f"{dev.device_path.replace(chr(92)*2+'.'+chr(92), '')}").classes(
                "text-weight-bold")

        ui.label(f"{dev.model}").classes("text-caption text-grey-5 q-ml-lg")

        with ui.row().classes("q-ml-lg gap-2"):
            if dev.serial:
                ui.label(f"S/N: {dev.serial[:20]}").classes("text-caption text-grey-6")
            ui.label(f"| {format_capacity(dev.capacity_bytes)}").classes("text-caption")
            for letter in dev.drive_letters:
                ui.badge(letter, color="primary").props("dense outline")

        if is_system:
            ui.badge("SYSTEM DRIVE — 操作不可", color="negative").props("dense").classes("q-mt-xs q-ml-lg")
