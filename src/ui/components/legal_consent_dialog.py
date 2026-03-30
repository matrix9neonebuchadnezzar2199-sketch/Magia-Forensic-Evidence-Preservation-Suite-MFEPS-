"""
MFEPS v2.0 — 法的免責事項 同意モーダル
コピーガード解析機能の利用前に表示
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from nicegui import ui

from src.models.database import session_scope
from src.models.schema import AppSettings
from src.services.audit_service import get_audit_service

logger = logging.getLogger("mfeps.legal_consent")

LEGAL_CONSENT_VERSION = "1.0"

LEGAL_TEXT = """\
【コピーガード解析機能に関する法的注意事項】

1. 目的
本ツール（MFEPS）のコピーガード解析機能は、デジタル・フォレンジック調査に\
おける証拠の完全性確保を目的として提供されています。

2. 日本国法との関係
コピーガード（技術的保護手段・技術的制限手段）の回避は、以下の法律により\
規制されています。
  ・不正競争防止法 第2条第18項（技術的制限手段の回避）
  ・著作権法 第30条第1項第2号（技術的保護手段の回避による複製の私的複製\
除外）

3. 本機能の性質
本機能はコピーガードの「検出・記録」を主目的としています。暗号化された\
メディアの復号コピーは、正当な法的権限に基づくフォレンジック証拠保全、\
または個人の研究・学術目的に限定して提供されるものであり、著作権侵害を\
目的とした複製を推奨・支援するものではありません。

4. 使用者の責任
使用者は、自国・地域の法令を遵守する責任を負います。本ツールの使用に\
起因する法的責任は、すべて使用者に帰属します。開発者は、使用者の行為に\
起因するいかなる法的責任も負いません。

5. 証拠能力
本ツールによるコピーガード検出結果は、フォレンジックレポートに記録されます。\
復号コピーを実施した場合、その旨と使用した復号手段が監査ログに記録されます。
"""

CONSENT_LABEL = (
    "上記内容を理解し、個人の研究またはフォレンジック証拠保全の"
    "目的のみで使用することに同意します。"
)


def is_consent_given() -> bool:
    """同意済みかどうかを確認（文言バージョン一致時のみ有効）"""
    with session_scope() as session:
        settings = session.query(AppSettings).first()
        if settings is None:
            return False
        return bool(
            settings.legal_consent_accepted
            and settings.legal_consent_version == LEGAL_CONSENT_VERSION
        )


def _on_scroll_to_bottom(e, checkbox: ui.checkbox) -> None:
    """スクロールが下端付近まで到達したらチェックボックスを有効化"""
    try:
        pct = getattr(e, "vertical_percentage", None)
        if pct is None:
            return
        if float(pct) >= 0.95:
            checkbox.enable()
    except Exception as ex:
        logger.debug("scroll handler: %s", ex)


def _save_consent() -> None:
    """同意をDBと監査ログに記録"""
    with session_scope() as session:
        settings = session.query(AppSettings).first()
        now = datetime.now(timezone.utc)

        if settings is None:
            settings = AppSettings(
                id=1,
                legal_consent_accepted=True,
                legal_consent_version=LEGAL_CONSENT_VERSION,
                legal_consent_at=now,
                legal_consent_actor="",
            )
            session.add(settings)
        else:
            settings.legal_consent_accepted = True
            settings.legal_consent_version = LEGAL_CONSENT_VERSION
            settings.legal_consent_at = now

    audit = get_audit_service()
    audit.add_entry(
        level="INFO",
        category="legal_consent",
        message="コピーガード解析機能の法的免責事項に同意",
        detail=f'{{"version": "{LEGAL_CONSENT_VERSION}"}}',
    )


async def show_legal_consent_dialog() -> bool:
    """
    法的免責モーダルを表示し、同意結果を返す。
    True: 同意 / False: 拒否またはキャンセル
    """
    with ui.dialog().props("persistent") as dialog, ui.card().classes(
        "w-full max-w-2xl"
    ):
        ui.label("⚖️ 法的免責事項").classes("text-h6 text-weight-bold q-mb-md")

        checkbox_ref: list[ui.checkbox | None] = [None]

        def _scroll_handler(e):
            cb = checkbox_ref[0]
            if cb is not None:
                _on_scroll_to_bottom(e, cb)

        with ui.scroll_area(on_scroll=_scroll_handler).classes(
            "w-full border rounded"
        ).style("height: 360px;"):
            ui.label(LEGAL_TEXT).classes("text-body2 whitespace-pre-wrap q-pa-md")

        checkbox = ui.checkbox(CONSENT_LABEL).classes("q-mt-md")
        checkbox_ref[0] = checkbox
        checkbox.disable()

        with ui.row().classes("full-width justify-end q-mt-md gap-2"):
            ui.button(
                "同意しない",
                on_click=lambda: dialog.submit(False),
                color="grey",
            ).props("flat")
            accept_btn = ui.button("同意する", color="primary").props("unelevated")
            accept_btn.disable()

        def _on_checkbox_change(e):
            if getattr(e, "value", False):
                accept_btn.enable()
            else:
                accept_btn.disable()

        checkbox.on_change(_on_checkbox_change)

        def _try_accept():
            if not checkbox.value:
                ui.notify("チェックボックスに同意してください", type="warning")
                return
            dialog.submit(True)

        accept_btn.on("click", _try_accept)

    result = await dialog

    if result is True:
        _save_consent()

    return bool(result)
