"""
MFEPS v2.1.0 — イメージングエンジン共通プロトコル
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class ImagingEngineProtocol(Protocol):
    """全イメージングエンジンが満たすべき最小インターフェース"""

    async def run(self, *args, **kwargs):
        """メインイメージングフローを実行"""
        ...

    async def cancel(self) -> None: ...

    async def pause(self) -> None: ...

    async def resume(self) -> None: ...
