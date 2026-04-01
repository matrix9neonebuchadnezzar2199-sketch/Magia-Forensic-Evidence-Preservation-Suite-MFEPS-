"""
MFEPS — NiceGUI app.storage の安全な読取ヘルパー

core / services から app.storage.general に触れる場合、NiceGUI 未初期化
（ユニットテスト・CLI 等）では例外になり得るため、try/except をここに集約する。

UI 層（pages/ 等）は NiceGUI が常に動作しているため、直接 app.storage を使ってよい。
"""
from __future__ import annotations

from typing import Any


def get_general_storage() -> dict:
    """app.storage.general を返す。NiceGUI 未初期化時は空 dict。"""
    try:
        from nicegui import app

        return app.storage.general
    except Exception:
        return {}


def get_storage_value(key: str, default: Any = None) -> Any:
    """app.storage.general から単一キーを取得。未初期化時は default。"""
    try:
        from nicegui import app

        return app.storage.general.get(key, default)
    except Exception:
        return default


def get_user_storage() -> dict:
    """app.storage.user を返す。未初期化時は空 dict（将来の統一用）。"""
    try:
        from nicegui import app

        return app.storage.user
    except Exception:
        return {}
