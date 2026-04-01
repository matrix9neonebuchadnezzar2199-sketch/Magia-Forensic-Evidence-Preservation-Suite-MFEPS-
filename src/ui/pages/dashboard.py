"""
MFEPS v2.1.0 — ダッシュボード画面
統計カード + 最近のジョブ一覧 + ディスク容量
"""
from nicegui import ui, app
from src.utils.constants import (
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_INFO,
)
from src.services.dashboard_service import get_dashboard_counts, get_recent_jobs


def build_dashboard():
    """ダッシュボードを構築"""
    ui.label("🏠 ダッシュボード").classes("text-h5 text-weight-bold q-mb-md")

    counts = get_dashboard_counts()
    n_cases = str(counts["cases"])
    n_ev = str(counts["evidence"])
    n_img = str(counts["images"])
    n_err = str(counts["errors"])

    # ---- 統計カード ----
    with ui.row().classes("gap-4 q-mb-lg full-width"):
        _stat_card("📁", "総案件数", n_cases, COLOR_PRIMARY)
        _stat_card("💾", "総証拠品数", n_ev, COLOR_INFO)
        _stat_card("📀", "総イメージ数", n_img, COLOR_SUCCESS)
        _stat_card("⚠️", "エラーセクタ合計", n_err, COLOR_WARNING)

    # ---- 最近のジョブ ----
    ui.label("最近のイメージングジョブ").classes("text-h6 q-mb-sm")

    columns = [
        {"name": "date", "label": "日時", "field": "date", "align": "left", "sortable": True},
        {"name": "case", "label": "案件番号", "field": "case", "align": "left"},
        {"name": "evidence", "label": "証拠品番号", "field": "evidence", "align": "left"},
        {"name": "media", "label": "メディア種別", "field": "media", "align": "center"},
        {"name": "status", "label": "ステータス", "field": "status", "align": "center"},
        {"name": "duration", "label": "所要時間", "field": "duration", "align": "right"},
    ]

    rows = get_recent_jobs(15)
    ui.table(
        columns=columns,
        rows=rows,
        row_key="id",
    ).classes("full-width").props("flat bordered")

    if not rows:
        with ui.row().classes("q-mt-md items-center"):
            ui.label(
                "ジョブがありません。サイドバーからイメージングを開始してください。"
            ).classes("text-caption text-grey-6")
    admin_hint = ""
    if not app.storage.general.get("is_admin", False):
        admin_hint = (
            " 管理者権限で起動していない場合、ブロックデバイスが検出されないことがあります。"
        )
    ui.label(
        f"統計はデータベースを参照しています。{admin_hint}"
    ).classes("text-caption text-grey-7 q-mt-sm")

    # ---- ディスク容量 ----
    ui.separator().classes("q-my-lg")
    ui.label("出力先ディスク容量").classes("text-h6 q-mb-sm")

    try:
        import psutil
        from src.utils.config import get_config
        config = get_config()
        usage = psutil.disk_usage(str(config.output_dir))
        used_percent = usage.percent
        free_gb = usage.free / (1024 ** 3)

        color = "positive" if free_gb > 10 else ("warning" if free_gb > 1 else "negative")

        with ui.card().classes("q-pa-md full-width"):
            ui.label(f"出力先: {config.output_dir}").classes("text-caption text-grey-5")
            ui.linear_progress(
                value=used_percent / 100,
                show_value=True,
                color=color,
            ).classes("q-mt-sm")
            with ui.row().classes("justify-between q-mt-xs"):
                ui.label(f"使用: {usage.used / (1024 ** 3):.1f} GB").classes("text-caption")
                ui.label(f"空き: {free_gb:.1f} GB / 合計: {usage.total / (1024 ** 3):.1f} GB").classes("text-caption")
    except Exception:
        ui.label("ディスク情報の取得に失敗しました").classes("text-caption text-grey-6")


def _stat_card(icon: str, label: str, value: str, color: str):
    """統計カードを作成"""
    with ui.card().classes("q-pa-md").style(
            f"min-width: 180px; border-left: 4px solid {color};"):
        with ui.row().classes("items-center gap-2"):
            ui.label(icon).classes("text-h5")
            with ui.column().classes("gap-0"):
                ui.label(value).classes("text-h4 text-weight-bold")
                ui.label(label).classes("text-caption text-grey-5")
