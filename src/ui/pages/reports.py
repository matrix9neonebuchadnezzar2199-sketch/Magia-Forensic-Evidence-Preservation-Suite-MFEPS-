"""
MFEPS v2.0 — レポート画面
報告書一覧 + 生成
"""
from nicegui import ui
import os
from pathlib import Path
from src.utils.config import get_config


def build_reports_page():
    """レポート画面"""
    ui.label("📄 レポート管理").classes("text-h5 text-weight-bold q-mb-md")

    # レポート一覧
    with ui.card().classes("q-pa-md full-width q-mb-md"):
        ui.label("既存レポート").classes("text-subtitle1 text-weight-bold q-mb-sm")

        config = get_config()
        reports_dir = config.reports_dir

        files = []
        if reports_dir.exists():
            for f in sorted(reports_dir.iterdir(), reverse=True):
                if f.suffix in (".pdf", ".html"):
                    size_kb = f.stat().st_size / 1024
                    files.append({
                        "name": f.name,
                        "type": f.suffix.upper(),
                        "size": f"{size_kb:.1f} KB",
                        "path": str(f),
                    })

        if files:
            columns = [
                {"name": "name", "label": "ファイル名", "field": "name", "align": "left", "sortable": True},
                {"name": "type", "label": "形式", "field": "type", "align": "center"},
                {"name": "size", "label": "サイズ", "field": "size", "align": "right"},
            ]
            ui.table(columns=columns, rows=files, row_key="name").classes(
                "full-width").props("flat bordered")
        else:
            ui.label("レポートがありません").classes("text-caption text-grey-6")

    # 新規レポート生成
    with ui.card().classes("q-pa-md full-width"):
        ui.label("新規レポート生成").classes("text-subtitle1 text-weight-bold q-mb-sm")
        ui.label("イメージングジョブ完了後に自動でレポートを生成できます").classes(
            "text-caption text-grey-5")

        with ui.row().classes("gap-2 q-mt-md"):
            ui.button("📊 全ジョブのレポート一括生成", color="primary").props("unelevated")
            ui.button("📁 レポートフォルダを開く").props("outline")
