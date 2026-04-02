"""Phase 3-1: optical_engine _image_optical_sync"""
from unittest.mock import patch

from src.core.optical_engine import (
    OpticalAnalysisResult,
    OpticalImagingEngine,
)


def _analysis(sectors: int = 0):
    return OpticalAnalysisResult(
        sector_count=sectors,
        sector_size=2048,
        capacity_bytes=max(0, sectors * 2048),
        capacity_source="test",
        media_type="DVD-Data",
    )


def test_zero_sectors_e8001(tmp_path):
    eng = OpticalImagingEngine()
    out = str(tmp_path / "o.iso")
    r = eng._image_optical_sync(
        r"\\.\CdRom0",
        out,
        _analysis(0),
    )
    assert r.status == "failed"
    assert r.error_code == "E8001"


def test_open_oserror_e8002(tmp_path):
    eng = OpticalImagingEngine()
    out = str(tmp_path / "o.iso")
    with patch(
        "src.core.optical_engine.open_device",
        side_effect=OSError("no"),
    ):
        r = eng._image_optical_sync(
            r"\\.\CdRom0",
            out,
            _analysis(100),
        )
    assert r.status == "failed"
    assert r.error_code == "E8002"
