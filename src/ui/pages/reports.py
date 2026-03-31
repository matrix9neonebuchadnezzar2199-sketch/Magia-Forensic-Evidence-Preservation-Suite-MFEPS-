"""
MFEPS v2.1.0 — レポート画面
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
            async def generate_all():
                from src.services.report_service import ReportService
                from src.models.database import session_scope
                from src.models.schema import ImagingJob

                ui.notify("レポート生成を開始しました...")
                try:
                    svc = ReportService()
                    with session_scope() as session:
                        jobs = session.query(ImagingJob).filter(
                            ImagingJob.status == "completed"
                        ).all()

                    count = 0
                    for job in jobs:
                        svc.generate_pdf(job.id)
                        svc.generate_html(job.id)
                        count += 1

                    ui.notify(f"{count}件のジョブレポートを生成しました", type="positive")
                    ui.timer(1.0, ui.navigate.reload, once=True)
                except Exception as e:
                    ui.notify(f"レポート生成エラー: {e}", type="negative")

            def open_reports_dir():
                import os, platform, subprocess
                from src.utils.config import get_config
                p = get_config().reports_dir
                p.mkdir(parents=True, exist_ok=True)
                if platform.system() == "Windows":
                    os.startfile(p)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", p])
                else:
                    subprocess.Popen(["xdg-open", p])

            ui.button("📊 全ジョブのレポート一括生成", on_click=generate_all, color="primary").props("unelevated")
            ui.button("📁 レポートフォルダを開く", on_click=open_reports_dir).props("outline")
