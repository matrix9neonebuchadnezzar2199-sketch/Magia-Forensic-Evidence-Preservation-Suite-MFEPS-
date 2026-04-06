"""NiceGUI 実行ループ参照（app.storage に置かない — JSON 永続化不可のため）"""
from __future__ import annotations

import asyncio
from typing import Optional

_loop: Optional[asyncio.AbstractEventLoop] = None


def set_nicegui_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def get_nicegui_loop() -> Optional[asyncio.AbstractEventLoop]:
    return _loop
