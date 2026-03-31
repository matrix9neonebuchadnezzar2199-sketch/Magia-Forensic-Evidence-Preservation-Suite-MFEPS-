"""
MFEPS v2.1.0 — 監査ログビューア画面
"""
from nicegui import ui
from src.services.audit_service import get_audit_service


def build_audit_page():
    """監査ログ画面"""
    ui.label("📋 監査ログ").classes("text-h5 text-weight-bold q-mb-md")

    audit_svc = get_audit_service()

    # ハッシュチェーン検証
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("■ ハッシュチェーン完全性検証").classes("text-subtitle1 text-weight-bold q-mb-sm")

        verify_result = ui.label("").classes("text-body2")

        async def on_verify():
            result = audit_svc.verify_chain()
            if result["valid"]:
                verify_result.text = f"✅ 完全性確認済み — {result['total_entries']} エントリ"
                verify_result.classes(replace="text-body2 text-positive")
            else:
                verify_result.text = f"❌ 改竄検出: {result.get('error', '不明')} (entry #{result.get('first_invalid_id', '?')})"
                verify_result.classes(replace="text-body2 text-negative")

        ui.button("🔍 チェーン検証", on_click=on_verify, color="primary").props("unelevated")

    # フィルタ
    with ui.row().classes("gap-2 q-mb-md items-end"):
        level_filter = ui.select(
            options=["すべて", "INFO", "WARN", "ERROR", "CRITICAL"],
            value="すべて",
            label="レベル",
        ).classes("min-w-32")
        category_filter = ui.select(
            options=["すべて", "system", "imaging", "hash", "coc", "auth", "config"],
            value="すべて",
            label="カテゴリ",
        ).classes("min-w-32")

        def refresh_table():
            level = (
                level_filter.value
                if level_filter.value != "すべて"
                else None
            )
            category = (
                category_filter.value
                if category_filter.value != "すべて"
                else None
            )
            new_entries = audit_svc.get_entries(
                limit=100, level=level, category=category
            )
            log_table.rows = new_entries
            log_table.update()
            ui.notify(f"{len(new_entries)} 件を表示", type="info")

        ui.button("🔄 更新", icon="refresh", on_click=refresh_table).props("outline")

    # ログテーブル
    columns = [
        {"name": "id", "label": "#", "field": "id", "align": "left", "sortable": True},
        {"name": "timestamp", "label": "日時", "field": "timestamp", "align": "left", "sortable": True},
        {"name": "level", "label": "レベル", "field": "level", "align": "center"},
        {"name": "category", "label": "カテゴリ", "field": "category", "align": "center"},
        {"name": "message", "label": "メッセージ", "field": "message", "align": "left"},
    ]

    entries = audit_svc.get_entries(limit=100)

    log_table = ui.table(columns=columns, rows=entries, row_key="id").classes(
        "full-width"
    ).props("flat bordered dense")

    # エクスポート
    with ui.row().classes("gap-2 q-mt-md"):
        def export_json():
            data = audit_svc.export_log(format="json")
            ui.download(data.encode("utf-8"), filename="audit_log.json")

        def export_csv():
            data = audit_svc.export_log(format="csv")
            ui.download(data.encode("utf-8"), filename="audit_log.csv")

        ui.button("📥 JSON エクスポート", on_click=export_json).props("outline")
        ui.button("📥 CSV エクスポート", on_click=export_csv).props("outline")
