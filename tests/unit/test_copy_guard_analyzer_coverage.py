"""copy_guard_analyzer の分岐カバレッジ（I/O なし・タイムアウト）"""
import time
from unittest.mock import patch

from src.core.copy_guard_analyzer import CopyGuardAnalyzer
from src.core.optical_engine import OpticalAnalysisResult, TrackInfo


def test_analyze_unknown_media_no_protection():
    an = CopyGuardAnalyzer()
    info = OpticalAnalysisResult(media_type="Unknown")
    r = an.analyze("Z:\\", info, timeout=0)
    assert "保護なし" in r.recommended_action
    assert r.protections == []


def test_analyze_cd_cccd_detected():
    an = CopyGuardAnalyzer()
    tracks = [
        TrackInfo(track_number=1, is_data=True),
        TrackInfo(track_number=2, is_data=False),
        TrackInfo(track_number=3, is_data=False),
    ]
    info = OpticalAnalysisResult(media_type="CD-ROM", track_count=3, tracks=tracks)
    r = an.analyze("Z:\\", info, timeout=0)
    assert len(r.protections) == 1
    assert r.protections[0].detected is True


def test_analyze_cd_cccd_not_detected():
    an = CopyGuardAnalyzer()
    info = OpticalAnalysisResult(
        media_type="CD-DA",
        track_count=1,
        tracks=[TrackInfo(track_number=1, is_data=False)],
    )
    r = an.analyze("Z:\\", info, timeout=0)
    assert len(r.protections) == 1
    assert r.protections[0].detected is False


def test_analyze_times_out():
    an = CopyGuardAnalyzer()
    info = OpticalAnalysisResult(media_type="Unknown")

    def slow(*_a, **_k):
        time.sleep(2)

    with patch.object(CopyGuardAnalyzer, "_analyze_body", side_effect=slow):
        r = an.analyze("Z:\\", info, timeout=0.05)
    assert "タイムアウト" in r.recommended_action
