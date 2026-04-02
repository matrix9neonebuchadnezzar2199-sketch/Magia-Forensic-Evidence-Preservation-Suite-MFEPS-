"""
MFEPS v2.1.0 — 光学メディア (CD/DVD/BD) ウィザードページ
4段階ウィザード + コピーガード解析結果表示
"""
import asyncio

from nicegui import ui, app

from src.core.device_detector import detect_optical_drives, OpticalDriveInfo
from src.core.optical_engine import OpticalMediaAnalyzer
from src.core.copy_guard_analyzer import CopyGuardAnalyzer, ProtectionInfo
from src.models.enums import CopyGuardType
from src.ui.components.legal_consent_dialog import (
    is_consent_given,
    show_legal_consent_dialog,
)
from src.ui.session_auth import get_current_actor_name
from src.utils.rbac import require_role


def build_optical_page():
    """光学メディアウィザード"""
    ui.label("💿 CD・DVD・BD イメージング").classes("text-h5 text-weight-bold q-mb-md")

    state = {
        "selected_drive": None,
        "analysis": None,
        "guard_result": None,
        "case_number": "",
        "evidence_number": "",
        "output_format": "ISO",
        "verify": False,
        "job_id": None,
        "result": None
    }

    with ui.stepper().classes("full-width").props("vertical animated") as stepper:

        # ===== STEP 1: ドライブ選択 =====
        with ui.step("ドライブ選択", icon="album"):
            ui.label("光学ドライブを選択してください").classes("text-body2 text-grey-5 q-mb-md")

            async def refresh_drives():
                drive_container.clear()
                state["selected_drive"] = None
                status_label.text = "🔍 ドライブ検出中..."
                drives = await asyncio.get_running_loop().run_in_executor(
                    None, detect_optical_drives)
                status_label.text = f"✅ {len(drives)} 台のドライブが検出されました"

                with drive_container:
                    for drv in drives:
                        _render_drive_option(drv, state)

            ui.button("🔄 ドライブ検出", on_click=refresh_drives, color="primary").props(
                "unelevated"
            ).classes("q-mb-md")

            drive_container = ui.column().classes("full-width gap-2")
            status_label = ui.label("").classes("text-caption text-grey-6")

            with ui.stepper_navigation():
                async def on_step1_next():
                    if not state.get("selected_drive"):
                        ui.notify("ドライブを選択してください", type="warning")
                        return
                    if not state["selected_drive"].media_loaded:
                        ui.notify("メディアが装填されていません", type="negative")
                        return

                    stepper.next()

                    if not is_consent_given():
                        accepted = await show_legal_consent_dialog()
                        if not accepted:
                            ui.notify(
                                "同意がないためコピーガード解析を実行できません",
                                type="warning",
                            )
                            stepper.previous()
                            return

                    # 分析フェーズ
                    scan_container.clear()
                    with scan_container:
                        ui.spinner(size="lg")
                        ui.label("メディア情報の解析とコピーガードを検出しています...")

                    analyzer = OpticalMediaAnalyzer()
                    drive_path = state["selected_drive"].device_path
                    pydvdcss_open = (
                        (state["selected_drive"].drive_letter or "").strip() or None
                    )
                    analysis = await asyncio.get_running_loop().run_in_executor(
                        None, analyzer.analyze, drive_path)
                    state["analysis"] = analysis

                    guard_analyzer = CopyGuardAnalyzer()
                    guard_result = await asyncio.get_running_loop().run_in_executor(
                        None,
                        lambda: guard_analyzer.analyze(
                            drive_path,
                            analysis,
                            pydvdcss_open_path=pydvdcss_open,
                        ),
                    )
                    state["guard_result"] = guard_result

                    scan_container.clear()
                    with scan_container:
                        ui.label(f"メディア種類: {analysis.media_type} ({analysis.file_system})").classes("text-body1 text-weight-bold")
                        ui.label(f"容量: {analysis.capacity_bytes / (1024**3):.2f} GiB").classes("text-caption text-grey-6")
                        render_copy_guard_badges(guard_result.protections)

                ui.button("次へ →", on_click=on_step1_next, color="primary").props("unelevated")

        # ===== STEP 2: プリスキャン + コピーガード解析 =====
        with ui.step("プリスキャン・コピーガード解析", icon="search"):
            scan_container = ui.column().classes("full-width")

            with ui.card().classes("q-pa-md full-width q-mt-md"):
                ui.label("コピー設定").classes("text-subtitle2 text-weight-bold q-mb-sm")

                with ui.row().classes("gap-4 items-center"):
                    ui.label("案件番号:").classes("text-body2")
                    case_input = ui.input(placeholder="CASE-001").classes("min-w-48")

                with ui.row().classes("gap-4 items-center q-mt-sm"):
                    ui.label("証拠品番号:").classes("text-body2")
                    ev_input = ui.input(placeholder="EV-001").classes("min-w-48")

                with ui.row().classes("gap-4 items-center q-mt-sm"):
                    ui.label("出力形式:").classes("text-body2")
                    format_select = ui.select(options=["ISO", "RAW (dd)"], value="ISO")

                verify_switch = ui.switch("二回読取検証（高信頼性）", value=False).classes("q-mt-sm")

                with ui.card().classes("q-pa-sm full-width q-mt-md").style(
                        "border-left: 3px solid #2196F3;"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("info", color="info", size="sm")
                        ui.label("書き込み保護について").classes(
                            "text-weight-bold text-info")
                    ui.label(
                        "光学メディアの読取は通常ライトブロック不要ですが、"
                        "リライタブルメディア（CD-RW, DVD-RW, BD-RE）の場合は "
                        "書き込みが可能なため注意が必要です。"
                        "報告書には書き込み保護方式が記録されます。"
                    ).classes("text-caption text-grey-5 q-mt-xs")

            with ui.stepper_navigation():
                ui.button("← 戻る", on_click=stepper.previous).props("flat")

                @require_role("examiner")
                async def start_copy():
                    case_val = case_input.value
                    ev_val = ev_input.value

                    if not case_val or not ev_val:
                        ui.notify("案件番号と証拠品番号を入力してください", type="warning")
                        return

                    from src.services.optical_service import get_optical_service
                    svc = get_optical_service()
                    if state.get("guard_result") is None:
                        ui.notify(
                            "コピーガード解析が完了していません。手前のステップからやり直してください。",
                            type="warning",
                        )
                        return
                    prots = state["guard_result"].protections
                    use_pydvdcss = any(
                        getattr(p.type, "value", p.type) == CopyGuardType.CSS.value
                        and p.can_decrypt
                        for p in prots
                    )
                    use_aacs = any(
                        getattr(p.type, "value", p.type) == CopyGuardType.AACS.value
                        and p.detected
                        and p.can_decrypt
                        for p in prots
                    )
                    g = app.storage.general
                    job_id = await svc.start_optical_imaging(
                        drive_path=state["selected_drive"].device_path,
                        case_id=case_val,
                        evidence_id=ev_val,
                        analysis=state["analysis"],
                        output_format=format_select.value,
                        use_pydvdcss=use_pydvdcss,
                        use_aacs=use_aacs,
                        verify=verify_switch.value,
                        actor_name=get_current_actor_name(),
                        hash_md5=g.get("hash_md5", True),
                        hash_sha1=g.get("hash_sha1", True),
                        hash_sha256=g.get("hash_sha256", True),
                        hash_sha512=g.get("hash_sha512", False),
                        pydvdcss_open_path=(
                            (state["selected_drive"].drive_letter or "").strip()
                            or None
                        ),
                    )
                    state["job_id"] = job_id

                    progress_container.clear()
                    log_area.clear()
                    log_area.push(f"[{job_id}] 光学メディアのイメージングを開始しました...")

                    if "timer" in state and state["timer"]:
                        state["timer"].active = False
                    state["timer"] = ui.timer(1.0, update_progress)
                    stepper.next()

                ui.button("▶️ コピー開始 →", on_click=start_copy, color="primary").props("unelevated")

        # ===== STEP 3: コピー実行 =====
        with ui.step("コピー実行", icon="content_copy"):
            ui.label("⚙️ コピー実行中").classes("text-h6 q-mb-md")

            progress_container = ui.column().classes("full-width")
            log_area = ui.log(max_lines=100).classes("full-width q-mt-md").style("height: 200px;")

            async def cancel_job():
                if state.get("job_id"):
                    from src.services.optical_service import get_optical_service
                    await get_optical_service().cancel_imaging(state["job_id"])
                    log_area.push("⚠️ ジョブをキャンセルしました")

            async def pause_job():
                if state.get("job_id"):
                    from src.services.optical_service import get_optical_service
                    await get_optical_service().pause_imaging(state["job_id"])
                    log_area.push("⏸ 一時停止しました")

            async def resume_job():
                if state.get("job_id"):
                    from src.services.optical_service import get_optical_service
                    await get_optical_service().resume_imaging(state["job_id"])
                    log_area.push("▶ 再開しました")

            with ui.row().classes("gap-2 q-mt-md"):
                ui.button("⏸ 一時停止", on_click=pause_job, icon="pause").props(
                    "outline"
                )
                ui.button("▶ 再開", on_click=resume_job, icon="play_arrow").props(
                    "outline"
                )
                ui.button("⏹ 中止", on_click=cancel_job, color="negative").props("outline")

            with ui.stepper_navigation():
                btn_next = ui.button("結果を確認 →", on_click=stepper.next, color="primary").props("unelevated")
                btn_next.disable()

            async def update_progress():
                if not state.get("job_id"):
                    return
                from src.services.optical_service import get_optical_service
                svc = get_optical_service()
                progress = svc.get_progress(state["job_id"])
                status = progress.get("status", "unknown")

                progress_container.clear()
                with progress_container:
                    from src.ui.components.progress_panel import (
                        render_progress_panel,
                        render_hash_display,
                        render_hash_comparison,
                    )
                    render_progress_panel(progress)
                    src_h = progress.get("source_hashes") or {}
                    ver_h = progress.get("verify_hashes") or {}
                    if src_h and ver_h:
                        render_hash_comparison(
                            src_h,
                            ver_h,
                            progress.get("match_result", "pending"),
                        )
                    elif src_h:
                        render_hash_display(src_h, "ソースハッシュ")

                if status in ["completed", "failed", "cancelled"]:
                    if "timer" in state and state["timer"]:
                        state["timer"].active = False
                        state["timer"] = None
                    btn_next.enable()
                    state["result"] = progress
                    build_result_page()

        # ===== STEP 4: リザルト =====
        with ui.step("リザルト", icon="check_circle"):
            ui.label("✅ コピー完了").classes("text-h6 q-mb-md")

            result_container = ui.column().classes("full-width")
            ui.label("結果はコピー実行後に表示されます").classes("text-caption text-grey-6")

            def build_result_page():
                result_container.clear()
                res = state.get("result", {})
                with result_container:
                    if res.get("status") == "completed":
                        ui.label("イメージングプロセスの結果レポート").classes("text-body1 q-mb-md")

                        src_hashes = res.get("source_hashes", {})
                        ver_hashes = res.get("verify_hashes", {})
                        if src_hashes and ver_hashes:
                            from src.ui.components.progress_panel import render_hash_comparison

                            render_hash_comparison(
                                src_hashes,
                                ver_hashes,
                                res.get("match_result", "pending"),
                            )
                        elif src_hashes:
                            from src.ui.components.progress_panel import render_hash_display

                            render_hash_display(
                                src_hashes,
                                "ソースハッシュ (検証なしまたは保留)",
                            )

                        inc_done = res.get("incomplete_files") or []
                        if inc_done:
                            from src.ui.components.progress_panel import (
                                render_incomplete_files_warning,
                            )

                            render_incomplete_files_warning(inc_done)

                        if res.get("error_count", 0) > 0:
                            from src.ui.components.progress_panel import render_error_panel
                            errors = [{"lba": s} for s in res.get("error_sectors", [])]
                            render_error_panel(errors)
                    else:
                        ui.label(
                            f"ジョブが正常に完了しませんでした "
                            f"({res.get('status', 'unknown')})"
                        ).classes("text-body1 text-negative")
                        inc_bad = res.get("incomplete_files") or []
                        if inc_bad:
                            from src.ui.components.progress_panel import (
                                render_incomplete_files_warning,
                            )

                            render_incomplete_files_warning(inc_bad)

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
                            description="光学メディア イメージング完了後の結果確認",
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


def _render_drive_option(drive: OpticalDriveInfo, state: dict):
    """光学ドライブ選択オプション"""
    media_color = "positive" if drive.media_loaded else "grey"
    border_color = media_color

    with ui.card().classes("q-pa-sm cursor-pointer full-width").style(
            f"border-left: 3px solid var(--q-{border_color});"):
        with ui.row().classes("items-center gap-2"):
            ui.radio(options=[drive.device_path], on_change=lambda e, d=drive: state.update({"selected_drive": d}))
            ui.icon("album")
            ui.label(f"{drive.drive_letter}").classes("text-weight-bold")
            ui.label(drive.drive_model).classes("text-caption text-grey-5")

        with ui.row().classes("q-ml-lg q-pl-lg items-center gap-1"):
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

            type_label = str(
                getattr(prot.type, "value", prot.type)
            ).upper()

            with ui.row().classes("items-center gap-2 q-mb-xs"):
                status = "🔴" if prot.detected and not prot.can_decrypt else (
                    "🟡" if prot.detected else "🟢")
                ui.label(status)
                ui.icon(icon, color=color, size="sm")
                ui.label(type_label).classes("text-weight-bold text-body2")
                ui.label(prot.details).classes("text-caption text-grey-5")
