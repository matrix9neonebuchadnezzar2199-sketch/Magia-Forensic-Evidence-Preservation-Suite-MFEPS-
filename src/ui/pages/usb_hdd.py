"""
MFEPS v2.0 — USB/HDD ウィザードページ
4段階ウィザード: ドライブ選択 → プリスキャン → コピー実行 → リザルト
"""
import asyncio
import logging
import uuid

from nicegui import ui, app

logger = logging.getLogger("mfeps.ui.usb_hdd")
from src.core.device_detector import detect_block_devices, DeviceInfo, format_capacity
from src.core.write_blocker import check_write_protection, get_protection_badge
from src.ui.components.progress_panel import (
    render_progress_panel, render_hash_comparison, render_error_panel, render_hash_display
)
from src.ui.layout import create_layout
from src.services.imaging_service import get_imaging_service
from src.ui.session_auth import get_current_actor_name


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
    wb_ui: dict = {}

    with ui.stepper().classes("full-width").props("vertical animated") as stepper:

        # ===== STEP 1: ドライブ選択 =====
        with ui.step("ドライブ選択", icon="usb"):
            ui.label("接続中のデバイスから対象を選択してください").classes("text-body2 text-grey-5 q-mb-md")

            async def refresh_devices():
                device_container.clear()
                state["selected_device"] = None
                if state.get("step1_next_btn"):
                    state["step1_next_btn"].disable()
                status_label.text = "🔍 デバイス検出中..."

                devices = await asyncio.get_running_loop().run_in_executor(
                    None, detect_block_devices)

                status_label.text = f"✅ {len(devices)} 台のデバイスが検出されました"

                with device_container:
                    for dev in devices:
                        _render_device_option(dev, state, stepper)

            # 一覧・次への直前に置かない（誤タップ防止）。説明文の直下。
            ui.button("🔄 デバイス検出", on_click=refresh_devices, color="primary").props(
                "unelevated"
            ).classes("q-mb-md")

            device_container = ui.column().classes("full-width gap-2")
            status_label = ui.label("").classes("text-caption text-grey-6")

            with ui.stepper_navigation():
                async def on_step1_next():
                    await check_write_block_status()
                    stepper.next()

                step1_next_btn = ui.button(
                    "次へ →", on_click=on_step1_next, color="primary"
                ).props("unelevated")
                step1_next_btn.disable()
                state["step1_next_btn"] = step1_next_btn

        # ===== STEP 2: プリスキャン・設定 =====
        with ui.step("プリスキャン・設定", icon="search"):
            ui.label("デバイス情報を確認し、コピー設定を行ってください").classes(
                "text-body2 text-grey-5 q-mb-md")

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

                with ui.row().classes("gap-4 items-center q-mt-sm"):
                    ui.label("出力形式:").classes("text-body2")
                    format_options = ["RAW (.dd)"]
                    format_values = ["raw"]
                    _e01_available = False
                    try:
                        from src.core.e01_writer import E01Writer

                        _e01_status = E01Writer.check_available()
                        _e01_available = _e01_status["ewfacquire_available"]
                    except Exception:
                        pass

                    if _e01_available:
                        format_options.append("E01 (Expert Witness)")
                        format_values.append("e01")

                    format_select = ui.select(
                        options={v: l for v, l in zip(format_values, format_options)},
                        value="raw",
                    ).classes("min-w-48")

                    if not _e01_available:
                        ui.label(
                            "E01 を使うには libs/ewfacquire.exe を配置するか、"
                            "設定 → E01 出力、または .env の EWFACQUIRE_PATH でパスを指定してください"
                        ).classes("text-caption text-grey-6")

                e01_panel = ui.column().classes("full-width q-mt-sm")
                e01_panel.visible = False

                with e01_panel:
                    with ui.card().classes("q-pa-sm full-width"):
                        ui.label("E01 設定").classes(
                            "text-subtitle2 text-weight-bold q-mb-xs"
                        )
                        with ui.row().classes("gap-4 items-center"):
                            ui.label("圧縮:").classes("text-body2")
                            e01_compression_select = ui.select(
                                options={
                                    "deflate:fast": "deflate / fast (推奨)",
                                    "deflate:best": "deflate / best (高圧縮)",
                                    "deflate:none": "deflate / none (無圧縮)",
                                    "deflate:empty-block": "deflate / empty-block",
                                },
                                value="deflate:fast",
                            ).classes("min-w-48")

                        with ui.row().classes("gap-4 items-center q-mt-xs"):
                            ui.label("鑑識者名:").classes("text-body2")
                            e01_examiner_input = ui.input(
                                placeholder="山田太郎"
                            ).classes("min-w-48")

                        with ui.row().classes("gap-4 items-center q-mt-xs"):
                            ui.label("説明:").classes("text-body2")
                            e01_description_input = ui.input(
                                placeholder="被疑者所有USBメモリ"
                            ).classes("min-w-48")

                def _on_format_change(_e):
                    e01_panel.visible = format_select.value == "e01"

                format_select.on_value_change(_on_format_change)

                wb_banner = ui.card().classes("q-pa-sm full-width q-mt-md").style(
                    "border-left: 3px solid #FF9800; display: none;")
                with wb_banner:
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("warning", color="warning", size="sm")
                        wb_title = ui.label("ソフトウェアライトブロック使用中").classes(
                            "text-weight-bold text-warning")
                    wb_body = ui.label(
                        "現在、レジストリ方式のソフトウェアライトブロックのみが有効です。"
                        "法廷証拠として提出する場合は、ハードウェアライトブロッカー"
                        "（Tableau, CRU 等）との併用を推奨します。"
                    ).classes("text-caption text-grey-5 q-mt-xs")
                wb_ui["banner"] = wb_banner
                wb_ui["title"] = wb_title
                wb_ui["body"] = wb_body

            async def check_write_block_status():
                if not state.get("selected_device"):
                    return
                wb = await asyncio.get_running_loop().run_in_executor(
                    None, check_write_protection, state["selected_device"].device_path)
                banner = wb_ui.get("banner")
                title = wb_ui.get("title")
                body = wb_ui.get("body")
                if not banner or not title or not body:
                    return
                if wb["registry_blocked"] and not wb["hardware_blocked"]:
                    title.text = "ソフトウェアライトブロック使用中"
                    body.text = (
                        "現在、レジストリ方式のソフトウェアライトブロックのみが有効です。"
                        "法廷証拠として提出する場合は、ハードウェアライトブロッカー"
                        "（Tableau, CRU 等）との併用を推奨します。"
                    )
                    banner.style(
                        replace="border-left: 3px solid #FF9800; display: block;")
                elif not wb["is_protected"]:
                    title.text = "書き込み保護なし"
                    body.text = (
                        "このデバイスに対して書き込み保護が検出されませんでした。"
                        "証拠保全として不適切な可能性があります。"
                    )
                    banner.style(
                        replace="border-left: 3px solid #FF5252; display: block;")
                else:
                    banner.style(replace="display: none;")

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
                    g = app.storage.general
                    job_id = await service.start_imaging(
                        device=state["selected_device"],
                        case_id=case_val,
                        evidence_id=ev_val,
                        output_format=format_select.value,
                        verify=verify_checkbox.value,
                        actor_name=get_current_actor_name(),
                        hash_md5=g.get("hash_md5", True),
                        hash_sha1=g.get("hash_sha1", True),
                        hash_sha256=g.get("hash_sha256", True),
                        hash_sha512=g.get("hash_sha512", False),
                        e01_examiner_name=(
                            e01_examiner_input.value
                            if format_select.value == "e01"
                            else ""
                        ),
                        e01_description=(
                            e01_description_input.value
                            if format_select.value == "e01"
                            else ""
                        ),
                        e01_notes="",
                        e01_compression=(
                            e01_compression_select.value
                            if format_select.value == "e01"
                            else ""
                        ),
                    )
                    state["job_id"] = job_id

                    # STEP 3 の初期化
                    progress_container.clear()
                    log_area.clear()
                    log_area.push(f"[{job_id}] イメージングジョブを開始しました...")

                    logger.debug("progress_timer を有効化 job_id=%s", job_id)
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

            async def pause_job():
                if state.get("job_id"):
                    await get_imaging_service().pause_imaging(state["job_id"])
                    log_area.push("⏸ 一時停止しました")
                    ui.notify("一時停止しました", type="info")

            async def resume_job():
                if state.get("job_id"):
                    await get_imaging_service().resume_imaging(state["job_id"])
                    log_area.push("▶ 再開しました")
                    ui.notify("再開しました", type="info")

            with ui.row().classes("gap-2 q-mt-md"):
                ui.button("⏸ 一時停止", on_click=pause_job, icon="pause").props(
                    "outline"
                )
                ui.button("▶ 再開", on_click=resume_job, icon="play_arrow").props(
                    "outline"
                )
                ui.button("⏹ 中止", on_click=cancel_job, icon="stop", color="negative").props("outline")

            with ui.stepper_navigation():
                btn_next = ui.button("結果を確認 →", on_click=stepper.next,
                         color="primary").props("unelevated")
                btn_next.disable()

            # ★ update_progress をここで定義（ページ構築スコープ内）
            def update_progress():
                logger.debug("progress tick job_id=%s", state.get("job_id"))
                if not state.get("job_id"):
                    return

                try:
                    service = get_imaging_service()
                    progress = dict(service.get_progress(state["job_id"]))
                    if "e01_percent" in progress:
                        pct_val = float(progress.get("e01_percent", 0))
                        dev = state.get("selected_device")
                        cap = dev.capacity_bytes if dev else 0
                        # E01 から acquired/total が来ているときは実測を優先
                        if progress.get("total_bytes", 0) <= 0 and cap > 0:
                            progress["copied_bytes"] = int(cap * pct_val / 100)
                            progress["total_bytes"] = cap
                    status = progress.get("status", "unknown")

                    progress_container.clear()
                    with progress_container:
                        render_progress_panel(progress)

                    if status in ["completed", "failed", "cancelled"]:
                        progress_timer.active = False
                        logger.debug("progress_timer 停止 status=%s", status)
                        state["result"] = progress
                        btn_next.enable()
                        build_result_page()

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

                    logger.exception("進捗更新エラー: %s", ex)
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
                            sec = state["selected_device"].sector_size if state.get(
                                "selected_device"
                            ) else 512
                            render_error_panel(
                                res.get("error_sectors", []),
                                sector_size=sec,
                            )
                    else:
                        ui.label(f"ジョブが正常に完了しませんでした ({res.get('status', 'unknown')})").classes("text-body1 text-negative")

            ui.label("結果はイメージングジョブ実行後に表示されます").classes(
                "text-caption text-grey-6")

            with ui.row().classes("gap-2 q-mt-lg"):
                async def generate_pdf():
                    if not state.get("job_id"):
                        ui.notify("ジョブIDがありません", type="warning")
                        return
                    try:
                        from src.services.report_service import ReportService

                        svc = ReportService()
                        pdf_path = svc.generate_pdf(state["job_id"])
                        ui.notify(
                            f"PDF 報告書を生成しました: {pdf_path}",
                            type="positive",
                        )
                    except Exception as e:
                        ui.notify(f"PDF 生成失敗: {e}", type="negative")

                async def add_coc_entry():
                    if not state.get("job_id"):
                        ui.notify("ジョブIDがありません", type="warning")
                        return
                    try:
                        from src.models.database import session_scope
                        from src.models.schema import ImagingJob
                        from src.services.coc_service import CoCService

                        with session_scope() as session:
                            job = session.get(ImagingJob, state["job_id"])
                            if not job:
                                ui.notify("ジョブが見つかりません", type="negative")
                                return
                            evidence_id = job.evidence_id

                        coc_svc = CoCService()
                        coc_svc.add_entry(
                            evidence_id=evidence_id,
                            action="report_reviewed",
                            actor_name=get_current_actor_name(),
                            description="USB/HDD イメージング完了後の結果確認",
                        )
                        ui.notify("CoC エントリを追加しました", type="positive")
                    except Exception as e:
                        ui.notify(f"CoC 追加失敗: {e}", type="negative")

                ui.button(
                    "📄 報告書PDF",
                    icon="picture_as_pdf",
                    color="primary",
                    on_click=generate_pdf,
                ).props("unelevated")
                ui.button(
                    "📋 CoC追加",
                    icon="link",
                    on_click=add_coc_entry,
                ).props("outline")
                ui.button(
                    "🏠 ダッシュボード",
                    icon="dashboard",
                    on_click=lambda: ui.navigate.to("/"),
                ).props("outline")


def _render_device_option(dev: DeviceInfo, state: dict, stepper):
    """デバイス選択オプションを表示"""
    is_system = dev.is_system_drive
    border_color = "#FF5252" if is_system else "rgba(108, 99, 255, 0.3)"

    card = ui.card().classes("q-pa-sm cursor-pointer full-width device-option").style(
        f"border-left: 3px solid {border_color}; transition: opacity 0.3s ease, border-color 0.3s ease;")

    with card:
        with ui.row().classes("items-center gap-2"):
            if not is_system:
                radio = ui.radio(
                    options=[dev.device_path],
                    on_change=lambda e, d=dev, c=card: _on_device_selected(d, c, state)
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


def _on_device_selected(dev: DeviceInfo, selected_card, state: dict):
    """デバイス選択時: 選択カードをハイライト、他を薄くする"""
    state.update({"selected_device": dev})

    # 親コンテナ内の全デバイスカードを取得して制御
    parent = selected_card.parent_slot.parent
    for child in parent:
        if hasattr(child, 'classes'):
            if child == selected_card:
                # 選択されたカード: ハイライト
                child.style(
                    replace="border-left: 3px solid #6C63FF; "
                    "opacity: 1; "
                    "box-shadow: 0 0 12px rgba(108, 99, 255, 0.4); "
                    "transition: opacity 0.3s ease, border-color 0.3s ease;")
            else:
                # 非選択カード: 薄く表示
                child.style(
                    replace="border-left: 3px solid rgba(108, 99, 255, 0.1); "
                    "opacity: 0.4; "
                    "transition: opacity 0.3s ease, border-color 0.3s ease;")

    ui.notify(f"✅ {dev.model} を選択しました", type="positive", position="bottom", timeout=2000)
    if state.get("step1_next_btn"):
        state["step1_next_btn"].enable()
