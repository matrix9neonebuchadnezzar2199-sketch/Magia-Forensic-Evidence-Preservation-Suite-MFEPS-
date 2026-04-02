"""ImagingEngineProtocol runtime_checkable"""
from src.core.engine_protocol import ImagingEngineProtocol


class _MinimalEngine:
    async def run(self, *args, **kwargs):
        pass

    async def cancel(self) -> None:
        pass

    async def pause(self) -> None:
        pass

    async def resume(self) -> None:
        pass


def test_runtime_checkable_engine():
    assert isinstance(_MinimalEngine(), ImagingEngineProtocol)
