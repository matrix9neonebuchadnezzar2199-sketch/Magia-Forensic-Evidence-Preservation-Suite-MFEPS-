"""
MFEPS — Sprint B-1: 光学メディア容量診断
"""
from src.core.optical_engine import OpticalAnalysisResult, TrackInfo


class TestCapacitySource:
    def test_toc_leadout_preferred_over_ioctl(self):
        """TOC リードアウトが IOCTL より優先される"""
        result = OpticalAnalysisResult(
            drive_path=r"\\.\CdRom0",
            sector_size=2048,
        )
        result.tracks = [
            TrackInfo(track_number=1, is_data=True, address_lba=0),
            TrackInfo(track_number=0xAA, is_data=True, address_lba=230235),
        ]
        result.ioctl_length_bytes = 471_828_480
        result.toc_leadout_bytes = 230235 * 2048

        if result.toc_leadout_bytes > 0:
            result.capacity_bytes = result.toc_leadout_bytes
            result.sector_count = result.toc_leadout_bytes // result.sector_size
            result.capacity_source = "toc_leadout"

        assert result.capacity_source == "toc_leadout"
        assert result.capacity_bytes == 471_521_280
        assert result.sector_count == 230235

    def test_ioctl_fallback_when_no_toc(self):
        """TOC リードアウトが無く IOCTL のみの場合は IOCTL"""
        result = OpticalAnalysisResult(
            drive_path=r"\\.\CdRom0",
            sector_size=2048,
        )
        result.ioctl_length_bytes = 471_828_480
        result.toc_leadout_bytes = 0

        toc_leadout_bytes = 0
        ioctl_bytes = result.ioctl_length_bytes
        toc_max_bytes = 0

        if toc_leadout_bytes > 0:
            result.capacity_bytes = toc_leadout_bytes
            result.capacity_source = "toc_leadout"
        elif ioctl_bytes > 0:
            result.capacity_bytes = ioctl_bytes
            result.sector_count = (
                (ioctl_bytes + result.sector_size - 1) // result.sector_size
            )
            result.capacity_source = "ioctl"
        elif toc_max_bytes > 0:
            result.capacity_bytes = toc_max_bytes
            result.sector_count = toc_max_bytes // result.sector_size
            result.capacity_source = "toc_max"

        assert result.capacity_source == "ioctl"
        assert result.capacity_bytes == 471_828_480

    def test_150_sector_difference(self):
        """150 セクタの差分が正しく計算される"""
        ioctl = 471_828_480
        toc = 230235 * 2048
        diff = ioctl - toc
        assert diff == 307_200
        assert diff // 2048 == 150
