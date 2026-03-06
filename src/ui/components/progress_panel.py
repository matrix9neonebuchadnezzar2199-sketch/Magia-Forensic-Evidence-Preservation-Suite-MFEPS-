"""
MFEPS v2.0 — プログレスバー / ハッシュ表示 / エラーパネル コンポーネント
"""
from nicegui import ui
from src.utils.constants import COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING


def render_progress_panel(progress: dict):
    """リアルタイム進捗パネル"""
    copied = progress.get("copied_bytes", 0)
    total = progress.get("total_bytes", 1)
    speed = progress.get("speed_mibps", 0)
    eta = progress.get("eta_seconds", 0)
    errors = progress.get("error_count", 0)
    status = progress.get("status", "idle")

    pct = (copied / total * 100) if total > 0 else 0

    with ui.card().classes("q-pa-md full-width"):
        # プログレスバー
        color = "positive" if errors == 0 else "warning"
        ui.linear_progress(
            value=pct / 100, show_value=False, color=color,
        ).classes("q-mb-sm").props("size=12px rounded")

        # パーセンテージ + バイト数
        with ui.row().classes("justify-between full-width"):
            ui.label(f"{pct:.1f}%").classes("text-h6 text-weight-bold")
            ui.label(
                f"{copied / (1024**3):.2f} / {total / (1024**3):.2f} GiB"
            ).classes("text-body2 text-grey-5")

        # 速度 / ETA / エラー
        with ui.row().classes("gap-4 q-mt-xs"):
            ui.label(f"⚡ {speed:.1f} MiB/s").classes("text-body2")
            m, s = divmod(int(eta), 60)
            h, m = divmod(m, 60)
            ui.label(f"⏱ 残り {h:02d}:{m:02d}:{s:02d}").classes("text-body2")
            color_cls = "text-grey-5" if errors == 0 else "text-warning"
            ui.label(f"⚠ エラー: {errors}").classes(f"text-body2 {color_cls}")


def render_hash_display(hashes: dict, label: str = "ハッシュ値"):
    """トリプルハッシュ表示"""
    with ui.card().classes("q-pa-md full-width"):
        ui.label(label).classes("text-subtitle2 text-weight-bold q-mb-sm")
        for algo in ["md5", "sha1", "sha256"]:
            value = hashes.get(algo, "")
            with ui.row().classes("items-center gap-2"):
                ui.badge(algo.upper(), color="primary").props("dense outline")
                ui.label(value or "計算中...").classes("hash-mono text-body2")


def render_hash_comparison(source: dict, verify: dict, match_result: str):
    """ソース vs イメージ ハッシュ照合結果"""
    with ui.card().classes("q-pa-md full-width"):
        ui.label("🔍 トリプルハッシュ検証").classes("text-subtitle1 text-weight-bold q-mb-md")

        for algo in ["md5", "sha1", "sha256"]:
            src_val = source.get(algo, "").lower()
            ver_val = verify.get(algo, "").lower()
            matched = src_val == ver_val and src_val != ""


            with ui.card().classes("q-pa-sm q-mb-xs").style(
                    f"border-left: 3px solid {COLOR_SUCCESS if matched else COLOR_ERROR};"):
                with ui.row().classes("items-center gap-2"):
                    ui.badge(algo.upper(), color="primary").props("dense outline")
                    icon = "check_circle" if matched else "cancel"
                    color = "positive" if matched else "negative"
                    ui.icon(icon, color=color, size="sm")

                ui.label(f"ソース: {src_val}").classes("hash-mono text-caption q-ml-lg")
                ui.label(f"イメージ: {ver_val}").classes("hash-mono text-caption q-ml-lg")

        # 総合判定
        all_match = match_result == "matched"
        with ui.row().classes("q-mt-md items-center gap-2"):
            if all_match:
                ui.icon("verified", color="positive", size="md")
                ui.label("🟢 全ハッシュ一致: 完全性確認済み").classes(
                    "text-subtitle1 text-weight-bold text-positive")
            else:
                ui.icon("error", color="negative", size="md")
                ui.label("🔴 ハッシュ不一致: 完全性に問題あり").classes(
                    "text-subtitle1 text-weight-bold text-negative")


def render_error_panel(errors: list[dict]):
    """エラーセクタパネル"""
    with ui.card().classes("q-pa-md full-width"):
        ui.label("⚠️ エラーセクタ").classes("text-subtitle2 text-weight-bold q-mb-sm")

        if not errors:
            ui.label("エラーセクタなし ✅").classes("text-body2 text-positive")
            return

        columns = [
            {"name": "lba", "label": "LBA", "field": "lba", "align": "left"},
            {"name": "offset", "label": "オフセット", "field": "offset", "align": "left"},
            {"name": "action", "label": "処理", "field": "action", "align": "center"},
        ]
        rows = [
            {"lba": s, "offset": f"0x{s * 512:X}", "action": "ゼロフィル"}
            for s in errors
        ]
        ui.table(columns=columns, rows=rows, row_key="lba").classes(
            "full-width").props("flat bordered dense")
