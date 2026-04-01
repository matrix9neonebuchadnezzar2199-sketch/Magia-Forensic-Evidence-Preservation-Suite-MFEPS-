"""
ハッシュ検証ページ — 完了ジョブの出力ファイルを再読取し、DB のソースハッシュと比較
"""
import asyncio
import json
from pathlib import Path

from nicegui import ui, app
from sqlalchemy import func

from src.core.hash_engine import verify_image_hash
from src.models.database import session_scope
from src.models.schema import HashRecord, ImagingJob


def _load_verifiable_jobs() -> list[dict]:
    """出力ファイルが存在するジョブ（E01 は除外）。"""
    with session_scope() as session:
        jobs = (
            session.query(ImagingJob)
            .filter(ImagingJob.output_path != "")
            .order_by(
                func.coalesce(
                    ImagingJob.completed_at, ImagingJob.started_at
                ).desc()
            )
            .limit(200)
            .all()
        )
    out = []
    for j in jobs:
        fmt = (j.output_format or "").lower()
        if fmt == "e01":
            continue
        p = (j.output_path or "").strip()
        if not p or not Path(p).is_file():
            continue
        out.append(
            {
                "id": j.id,
                "label": f"{j.id[:8]}… — {Path(p).name} ({fmt or 'raw'})",
                "path": p,
                "format": fmt,
            }
        )
    return out


def _load_source_hashes(job_id: str) -> dict | None:
    with session_scope() as session:
        rec = (
            session.query(HashRecord)
            .filter(
                HashRecord.job_id == job_id,
                HashRecord.target == "source",
            )
            .first()
        )
        if not rec:
            return None
        h = {}
        if (rec.md5 or "").strip():
            h["md5"] = rec.md5.strip().lower()
        if (rec.sha1 or "").strip():
            h["sha1"] = rec.sha1.strip().lower()
        if (rec.sha256 or "").strip():
            h["sha256"] = rec.sha256.strip().lower()
        if (rec.sha512 or "").strip():
            h["sha512"] = rec.sha512.strip().lower()
        return h if h else None


def build_hash_verify_page():
    ui.label("🔑 ハッシュ検証").classes("text-h5 text-weight-bold q-mb-md")
    ui.label(
        "完了したイメージングジョブを選び、出力ファイルを再読取して "
        "記録済みソースハッシュと照合します（E01 はセグメント形式のため対象外）。"
    ).classes("text-body2 text-grey-6 q-mb-md")

    jobs = _load_verifiable_jobs()
    if not jobs:
        ui.label(
            "検証可能なジョブがありません。RAW / ISO 等の出力ファイルが存在し、"
            "ソースハッシュが記録されている必要があります。"
        ).classes("text-warning")
        return

    options = {j["label"]: j["id"] for j in jobs}
    job_by_id = {j["id"]: j for j in jobs}

    selected_id: dict[str, str | None] = {"v": None}
    result_container = ui.column().classes("full-width")

    job_select = ui.select(
        list(options.keys()),
        label="イメージングジョブ",
    ).classes("full-width max-w-2xl")

    def _on_job_pick(_):
        for lbl, jid in options.items():
            if lbl == job_select.value:
                selected_id["v"] = jid
                break

    job_select.on("update:model-value", _on_job_pick)
    if options:
        first_lbl = next(iter(options.keys()))
        job_select.value = first_lbl
        selected_id["v"] = options[first_lbl]

    g = app.storage.general

    with ui.row().classes("items-center gap-4 q-my-md flex-wrap"):
        ui.checkbox(
            "MD5",
            value=g.get("hash_md5", True),
            on_change=lambda e: g.update({"hash_md5": e.sender.value}),
        )
        ui.checkbox(
            "SHA-1",
            value=g.get("hash_sha1", True),
            on_change=lambda e: g.update({"hash_sha1": e.sender.value}),
        )
        ui.checkbox(
            "SHA-256",
            value=g.get("hash_sha256", True),
            on_change=lambda e: g.update({"hash_sha256": e.sender.value}),
        )
        ui.checkbox(
            "SHA-512",
            value=g.get("hash_sha512", False),
            on_change=lambda e: g.update({"hash_sha512": e.sender.value}),
        )

    progress_bar = ui.linear_progress(value=0, show_value=False).classes(
        "full-width max-w-2xl"
    )
    progress_bar.visible = False

    async def run_verify():
        jid = selected_id["v"]
        if not jid:
            ui.notify("ジョブを選択してください", type="warning")
            return
        expected = _load_source_hashes(jid)
        if not expected:
            ui.notify(
                "このジョブにソースハッシュ記録がありません", type="warning"
            )
            return
        info = job_by_id.get(jid)
        if not info:
            return
        path = info["path"]
        if not Path(path).is_file():
            ui.notify("出力ファイルが見つかりません", type="negative")
            return

        h_md5 = g.get("hash_md5", True)
        h_sha1 = g.get("hash_sha1", True)
        h_sha256 = g.get("hash_sha256", True)
        h_sha512 = g.get("hash_sha512", False)

        result_container.clear()
        progress_bar.visible = True
        progress_bar.value = 0.05

        loop = asyncio.get_running_loop()

        def _work():
            return verify_image_hash(
                path,
                expected,
                buffer_size=1_048_576,
                progress_callback=None,
                md5=h_md5,
                sha1=h_sha1,
                sha256=h_sha256,
                sha512=h_sha512,
            )

        try:
            vres = await loop.run_in_executor(None, _work)
        except Exception as e:
            progress_bar.visible = False
            ui.notify(f"検証エラー: {e}", type="negative")
            return
        finally:
            progress_bar.visible = False
            progress_bar.value = 0

        computed = vres.get("computed") or {}
        match = vres.get("all_match", False)

        with result_container:
            from src.ui.components.progress_panel import render_hash_comparison

            render_hash_comparison(
                expected,
                computed,
                "matched" if match else "mismatched",
            )
            detail = {
                "job_id": jid,
                "path": path,
                "algorithms": {
                    "md5": h_md5,
                    "sha1": h_sha1,
                    "sha256": h_sha256,
                    "sha512": h_sha512,
                },
                "per_algo": {
                    k: vres.get(k)
                    for k in vres
                    if k.endswith("_match")
                },
            }
            ui.label(json.dumps(detail, ensure_ascii=False, indent=2)).classes(
                "text-caption hash-mono q-mt-md full-width overflow-auto"
            )

        ui.notify(
            "検証: 全ハッシュ一致" if match else "検証: 不一致あり",
            type="positive" if match else "negative",
        )

    ui.button(
        "再読取して検証",
        on_click=run_verify,
        icon="verified",
        color="primary",
    ).props("unelevated").classes("q-mt-sm")
