"""
MFEPS v2.0 — CoC (Chain of Custody) 管理画面
"""
from nicegui import ui
from src.services.coc_service import CoCService
from src.services.case_service import CaseService, EvidenceService


def build_coc_page():
    """CoC管理画面"""
    ui.label("⛓️ Chain of Custody").classes("text-h5 text-weight-bold q-mb-md")

    # 案件・証拠品選択
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ 案件・証拠品選択").classes("text-subtitle1 text-weight-bold q-mb-sm")

        case_svc = CaseService()
        cases = case_svc.get_all_cases()

        if cases:
            case_options = {c["id"]: f"{c['case_number']} - {c['case_name']}" for c in cases}
            ui.select(
                options=case_options, label="案件",
            ).classes("full-width q-mb-sm")
        else:
            ui.label("案件がありません。イメージングを実行してください。").classes(
                "text-caption text-grey-6")

    # CoC タイムライン
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ CoC タイムライン").classes("text-subtitle1 text-weight-bold q-mb-sm")

        ui.label("証拠品を選択するとタイムラインが表示されます").classes(
            "text-caption text-grey-6")

        # タイムラインのプレースホルダー
        with ui.timeline(side="right").classes("q-mt-md"):
            with ui.timeline_entry(title="証拠品作成", subtitle="2024-01-01 10:00:00",
                                   icon="add_circle", color="primary"):
                ui.label("サンプルエントリ").classes("text-caption")

    # エントリ追加 + エクスポート
    with ui.row().classes("gap-2 q-mt-md"):
        ui.button("➕ CoC エントリ追加", color="primary").props("unelevated")
        ui.button("📥 JSON エクスポート").props("outline")
        ui.button("📥 CSV エクスポート").props("outline")
