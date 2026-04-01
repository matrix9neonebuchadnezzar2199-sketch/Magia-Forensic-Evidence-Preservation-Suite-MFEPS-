"""
MFEPS — Sprint B-1: 光学メディア容量診断 + DVD IOCTL 優先
"""
from src.core.optical_engine import OpticalAnalysisResult, OpticalMediaAnalyzer, TrackInfo


class TestCapacitySource:
    def test_toc_leadout_preferred_over_ioctl(self):
        """CD 系: TOC リードアウトが IOCTL より優先される"""
        analyzer = OpticalMediaAnalyzer()
        result = OpticalAnalysisResult(
            drive_path=r"\\.\CdRom0",
            sector_size=2048,
        )
        result.tracks = [
            TrackInfo(track_number=1, is_data=True, address_lba=0),
            TrackInfo(track_number=0xAA, is_data=True, address_lba=230235),
        ]
        ioctl_bytes = 471_828_480
        toc_leadout_bytes = 230235 * 2048

        analyzer._fill_optical_capacity(
            result,
            ioctl_bytes,
            toc_leadout_bytes,
            0,
            prefer_ioctl_first=False,
        )

        assert result.capacity_source == "toc_leadout"
        assert result.capacity_bytes == 471_521_280
        assert result.sector_count == 230235

    def test_ioctl_fallback_when_no_toc(self):
        """TOC リードアウトが無く IOCTL のみの場合は IOCTL"""
        analyzer = OpticalMediaAnalyzer()
        result = OpticalAnalysisResult(
            drive_path=r"\\.\CdRom0",
            sector_size=2048,
        )
        result.ioctl_length_bytes = 471_828_480
        toc_leadout_bytes = 0

        analyzer._fill_optical_capacity(
            result,
            result.ioctl_length_bytes,
            toc_leadout_bytes,
            0,
            prefer_ioctl_first=False,
        )

        assert result.capacity_source == "ioctl"
        assert result.capacity_bytes == 471_828_480

    def test_150_sector_difference(self):
        """150 セクタの差分が正しく計算される"""
        ioctl = 471_828_480
        toc = 230235 * 2048
        diff = ioctl - toc
        assert diff == 307_200
        assert diff // 2048 == 150

    def test_dvd_ioctl_preferred_over_toc(self):
        """DVD 以上: IOCTL が TOC リードアウトより優先（不正な大きい TOC を無視）"""
        analyzer = OpticalMediaAnalyzer()
        result = OpticalAnalysisResult(
            drive_path=r"\\.\CdRom0",
            sector_size=2048,
        )
        result.tracks = [
            TrackInfo(track_number=1, is_data=True, address_lba=0),
            TrackInfo(track_number=0xAA, is_data=True, address_lba=50_000_000),
        ]
        toc_leadout_bytes = 50_000_000 * 2048
        ioctl_bytes = 4_700_000_000

        analyzer._fill_optical_capacity(
            result,
            ioctl_bytes,
            toc_leadout_bytes,
            0,
            prefer_ioctl_first=True,
        )

        assert result.capacity_source == "ioctl"
        assert result.capacity_bytes == ioctl_bytes

    def test_sub_700mb_ioctl_still_prefers_toc_when_cd_order(self):
        """IOCTL が 700MB 未満なら CD 優先順（TOC > IOCTL）— TOC が選ばれる"""
        analyzer = OpticalMediaAnalyzer()
        result = OpticalAnalysisResult(
            drive_path=r"\\.\CdRom0",
            sector_size=2048,
        )
        toc_leadout_bytes = 400_000_000
        ioctl_bytes = 500_000_000

        analyzer._fill_optical_capacity(
            result,
            ioctl_bytes,
            toc_leadout_bytes,
            0,
            prefer_ioctl_first=False,
        )

        assert result.capacity_source == "toc_leadout"
        assert result.capacity_bytes == toc_leadout_bytes

    def test_bd_size_uses_ioctl_when_prefer_ioctl(self):
        """大容量ディスク: IOCTL 優先で BD 級バイト数を採用"""
        analyzer = OpticalMediaAnalyzer()
        result = OpticalAnalysisResult(
            drive_path=r"\\.\CdRom0",
            sector_size=2048,
        )
        ioctl_bytes = 26_000_000_000
        toc_leadout_bytes = 30_000_000_000

        analyzer._fill_optical_capacity(
            result,
            ioctl_bytes,
            toc_leadout_bytes,
            0,
            prefer_ioctl_first=True,
        )

        assert result.capacity_source == "ioctl"
        assert result.capacity_bytes == ioctl_bytes
