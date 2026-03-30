"""copy_guard_analyzer の軽量テスト（I/O なし）"""
from src.core.copy_guard_analyzer import CopyGuardAnalyzer
from src.core.optical_engine import OpticalAnalysisResult


def test_cccd_not_detected_on_empty_tracks():
    info = OpticalAnalysisResult(media_type="CD-ROM", track_count=1, tracks=[])
    r = CopyGuardAnalyzer()._check_cccd("D:", info)
    assert r.detected is False
