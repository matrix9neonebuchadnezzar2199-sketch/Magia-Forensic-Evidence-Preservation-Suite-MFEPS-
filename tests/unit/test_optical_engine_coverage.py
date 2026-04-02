"""optical_engine.py の追加カバレッジ"""
import asyncio

from src.core.optical_engine import (
    OpticalAnalysisResult,
    OpticalImagingEngine,
    OpticalImagingResult,
    OpticalMediaAnalyzer,
)


def test_optical_analysis_result_defaults():
    r = OpticalAnalysisResult()
    assert r.media_type == "Unknown"
    assert r.capacity_bytes == 0
    assert r.tracks == []


def test_optical_imaging_result_defaults():
    r = OpticalImagingResult()
    assert r.status == "completed"
    assert r.copied_bytes == 0
    assert r.source_hashes == {}


def test_optical_engine_cancel():
    async def _run():
        engine = OpticalImagingEngine()
        await engine.cancel()
        return engine._cancel_event.is_set()

    assert asyncio.run(_run()) is True


def test_optical_engine_pause_resume():
    async def _run():
        engine = OpticalImagingEngine()
        await engine.pause()
        await engine.resume()
        return engine._pause_event.is_set()

    assert asyncio.run(_run()) is True


def test_optical_media_analyzer_init():
    a = OpticalMediaAnalyzer()
    assert a is not None
