"""
MFEPS v2.3.0 — ケース / 証拠品管理ページ
"""
from nicegui import ui

from src.models.database import session_scope
from src.models.schema import ImagingJob
from src.services.case_service import CaseService, EvidenceService
from src.utils.rbac import has_permission, require_role


def build_cases_page():
    """ケース管理画面"""
    ui.label("📁 ケース管理").classes("text-h5 text-weight-bold q-mb-md")

    case_svc = CaseService()
    body = ui.column().classes("full-width")

    def refresh():
        body.clear()
        cases = case_svc.get_all_cases()
        with body:
            if not cases:
                ui.label("ケースがありません").classes("text-caption text-grey-6")
                return

            for c in cases:
                _render_case_card(c, refresh)

    refresh()

    if has_permission("examiner"):
        ui.separator().classes("q-my-md")
        ui.label("新規ケース作成").classes("text-subtitle1 text-weight-bold")
        cn = ui.input("案件番号", placeholder="CASE-2026-001").classes("q-mt-sm")
        cname = ui.input("案件名", placeholder="事件名称")
        examiner = ui.input("鑑識者名", placeholder="山田太郎")
        desc = ui.textarea("備考", placeholder="任意").classes("full-width")

        @require_role("examiner")
        async def create():
            if not cn.value or not cname.value:
                ui.notify("案件番号と案件名を入力してください", type="warning")
                return
            try:
                case_svc.create_case(
                    cn.value.strip(),
                    cname.value.strip(),
                    examiner.value.strip() if examiner.value else "",
                    desc.value.strip() if desc.value else "",
                )
                ui.notify("ケースを作成しました", type="positive")
                cn.value = ""
                cname.value = ""
                examiner.value = ""
                desc.value = ""
                refresh()
            except Exception as e:
                ui.notify(f"作成失敗: {e}", type="negative")

        ui.button("作成", on_click=create, color="primary", icon="add").props(
            "unelevated"
        ).classes("q-mt-md")


def _render_case_card(case_data: dict, refresh_fn):
    """ケースカードを描画"""
    cid = case_data["id"]
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        with ui.row().classes("items-center justify-between full-width"):
            ui.label(
                f"📁 {case_data['case_number']}: {case_data['case_name']}"
            ).classes("text-subtitle1 text-weight-bold")
            ui.badge(case_data["status"], color="primary").props("dense outline")

        ui.label(
            f"鑑識者: {case_data.get('examiner_name') or '未記入'}"
        ).classes("text-caption text-grey-5")
        ui.label(
            f"証拠品数: {case_data.get('evidence_count', 0)}  |  "
            f"作成日: {case_data['created_at']}"
        ).classes("text-caption text-grey-6")

        with ui.expansion("証拠品・ジョブ一覧", icon="inventory").classes(
            "full-width q-mt-sm"
        ):
            ev_svc = EvidenceService()
            evidences = ev_svc.get_evidence_by_case(cid)
            if not evidences:
                ui.label("証拠品なし").classes("text-caption text-grey-6")
            else:
                for ev in evidences:
                    _render_evidence_row(ev)

        if has_permission("admin"):
            with ui.row().classes("gap-2 q-mt-sm"):

                async def do_delete(case_id=cid):
                    svc = CaseService()
                    if svc.delete_case(case_id):
                        ui.notify("ケースを削除しました", type="positive")
                        refresh_fn()
                    else:
                        ui.notify("削除失敗", type="negative")

                ui.button(
                    "削除", on_click=do_delete, icon="delete", color="negative"
                ).props("dense outline size=sm")


def _render_evidence_row(ev: dict):
    """証拠品行を描画（ジョブ一覧含む）"""
    with ui.card().classes("q-pa-sm full-width q-mb-xs").style(
        "border-left: 3px solid rgba(108, 99, 255, 0.3);"
    ):
        ui.label(
            f"💾 {ev['evidence_number']} ({ev.get('media_type') or '—'})"
        ).classes("text-weight-bold text-body2")
        serial = (ev.get("device_serial") or "—")[:20]
        cap = ev.get("capacity_bytes") or 0
        ui.label(
            f"モデル: {ev.get('device_model') or '—'} | "
            f"S/N: {serial} | "
            f"容量: {cap:,} bytes"
        ).classes("text-caption text-grey-6")

        with session_scope() as session:
            jobs = (
                session.query(ImagingJob)
                .filter_by(evidence_id=ev["id"])
                .order_by(ImagingJob.started_at.desc())
                .all()
            )
            if jobs:
                for j in jobs:
                    status_icon = {
                        "completed": "✅",
                        "failed": "❌",
                        "cancelled": "⚠️",
                    }.get(j.status, "⏳")
                    dt_str = (
                        j.completed_at.strftime("%Y-%m-%d %H:%M")
                        if j.completed_at
                        else "—"
                    )
                    spd = float(j.avg_speed_mbps or 0)
                    ui.label(
                        f"  {status_icon} {(j.output_format or 'raw').upper()} | "
                        f"{j.status} | {dt_str} | "
                        f"{spd:.1f} MiB/s"
                    ).classes("text-caption q-ml-md")
