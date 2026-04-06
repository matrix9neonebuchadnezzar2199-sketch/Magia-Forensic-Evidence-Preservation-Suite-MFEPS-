"""
MFEPS v2.1.0 — CoC (Chain of Custody) 管理画面
"""
from nicegui import ui

from src.models.database import session_scope
from src.models.schema import EvidenceItem
from src.services.coc_service import CoCService
from src.services.case_service import CaseService, EvidenceService
from src.utils.reports_paths import case_reports_dir


def build_coc_page():
    """CoC管理画面"""
    ui.label("⛓️ Chain of Custody").classes("text-h5 text-weight-bold q-mb-md")

    state = {"selected_case": None, "selected_evidence": None}

    # 案件・証拠品選択
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ 案件・証拠品選択").classes("text-subtitle1 text-weight-bold q-mb-sm")

        case_svc = CaseService()
        cases = case_svc.get_all_cases()
        ev_svc = EvidenceService()

        def on_case_select(e):
            state["selected_case"] = e.value
            evs = ev_svc.get_evidence_by_case(e.value)
            ev_options = {ev["id"]: ev["evidence_number"] for ev in evs}
            ev_select.options = ev_options
            ev_select.value = None
            ev_select.update()
            state["selected_evidence"] = None
            render_timeline()

        def on_ev_select(e):
            state["selected_evidence"] = e.value
            render_timeline()

        if cases:
            case_options = {c["id"]: f"{c['case_number']} - {c['case_name']}" for c in cases}
            ui.select(
                options=case_options, label="案件", on_change=on_case_select
            ).classes("full-width q-mb-sm")
            ev_select = ui.select(options={}, label="証拠品", on_change=on_ev_select).classes("full-width")
        else:
            ui.label("案件がありません。イメージングを実行してください。").classes(
                "text-caption text-grey-6")

    # CoC タイムライン
    timeline_card = ui.card().classes("q-pa-md full-width q-mb-md")
    with timeline_card:
        ui.label("■ CoC タイムライン").classes("text-subtitle1 text-weight-bold q-mb-sm")
        timeline_container = ui.column().classes("full-width")

    def render_timeline():
        timeline_container.clear()
        if not state.get("selected_evidence"):
            with timeline_container:
                ui.label("証拠品を選択するとタイムラインが表示されます").classes("text-caption text-grey-6")
            return

        coc_svc = CoCService()
        entries = coc_svc.get_entries(state["selected_evidence"])

        with timeline_container:
            if not entries:
                ui.label("この証拠品の履歴はまだありません").classes("text-caption text-grey-5")
                return

            with ui.timeline(side="right").classes("q-mt-md full-width"):
                for ent in entries:
                    ui.timeline_entry(
                        title=f"{ent['action']} - {ent['actor_name']}",
                        subtitle=ent['timestamp'][:19],  # "YYYY-MM-DD HH:MM:SS"
                        body=ent['description'],
                        icon="info",
                        color="primary"
                    )

    # 初回描画
    render_timeline()

    # エントリ追加 + エクスポート
    with ui.row().classes("gap-2 q-mt-md"):
        async def add_entry_dialog():
            if not state.get("selected_evidence"):
                ui.notify("証拠品を選択してください", type="warning")
                return

            with ui.dialog() as dialog, ui.card():
                ui.label("手動エントリの追加").classes("text-h6")
                action_input = ui.input("アクション名 (例: 移管, 鑑定)")
                actor_input = ui.input("実行者名")
                desc_input = ui.textarea("詳細説明").classes("w-full")
                with ui.row().classes("q-mt-md"):
                    ui.button("キャンセル", on_click=dialog.close).props("flat")
                    def _submit():
                        if action_input.value and actor_input.value:
                            coc_svc = CoCService()
                            coc_svc.add_entry(
                                state["selected_evidence"],
                                action_input.value,
                                actor_input.value,
                                desc_input.value or ""
                            )
                            ui.notify("CoCエントリを追加しました", type="positive")
                            render_timeline()
                            dialog.close()
                        else:
                            ui.notify("アクション名と実行者名は必須です", type="negative")
                    ui.button("追加", on_click=_submit).props("unelevated color=primary")

            dialog.open()

        def _resolve_case_for_export():
            case_svc = CaseService()
            cid = state.get("selected_case")
            if not cid and state.get("selected_evidence"):
                with session_scope() as session:
                    ev = session.get(EvidenceItem, state["selected_evidence"])
                    if ev:
                        cid = ev.case_id
            if not cid:
                return None
            return case_svc.get_case(cid)

        def export_json():
            if not state.get("selected_evidence"):
                return ui.notify("証拠品を選択してください", type="warning")
            case_row = _resolve_case_for_export()
            if not case_row:
                return ui.notify("案件を特定できません", type="warning")
            coc_svc = CoCService()
            text = coc_svc.export(state["selected_evidence"], format="json")
            out_dir = case_reports_dir(
                case_row["case_name"], case_number=case_row["case_number"]
            )
            filename = f"coc_export_{state['selected_evidence']}.json"
            out_path = out_dir / filename
            out_path.write_text(text, encoding="utf-8")
            ui.notify(f"保存しました: {out_path}", type="positive")
            ui.download(out_path.read_bytes(), filename=filename)

        def export_csv():
            if not state.get("selected_evidence"):
                return ui.notify("証拠品を選択してください", type="warning")
            case_row = _resolve_case_for_export()
            if not case_row:
                return ui.notify("案件を特定できません", type="warning")
            coc_svc = CoCService()
            text = coc_svc.export(state["selected_evidence"], format="csv")
            out_dir = case_reports_dir(
                case_row["case_name"], case_number=case_row["case_number"]
            )
            filename = f"coc_export_{state['selected_evidence']}.csv"
            out_path = out_dir / filename
            out_path.write_text(text, encoding="utf-8")
            ui.notify(f"保存しました: {out_path}", type="positive")
            ui.download(out_path.read_bytes(), filename=filename)

        ui.button("➕ CoC エントリ追加", on_click=add_entry_dialog, color="primary").props("unelevated")
        ui.button("📥 JSON エクスポート", on_click=export_json).props("outline")
        ui.button("📥 CSV エクスポート", on_click=export_csv).props("outline")
