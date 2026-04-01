"""format_helpers のユニットテスト"""
from src.utils.format_helpers import format_capacity


class TestFormatCapacity:
    def test_tb(self):
        assert format_capacity(2 * 1024**4) == "2.00 TB"

    def test_gb(self):
        assert format_capacity(4_000_000_000) == "3.73 GB"

    def test_mb(self):
        assert format_capacity(10 * 1024**2) == "10.00 MB"

    def test_kb(self):
        assert format_capacity(2048) == "2.00 KB"

    def test_bytes(self):
        assert format_capacity(512) == "512 B"

    def test_zero(self):
        assert format_capacity(0) == "不明"

    def test_negative(self):
        assert format_capacity(-100) == "不明"

    def test_exact_boundary_gb(self):
        assert format_capacity(1024**3) == "1.00 GB"

    def test_backward_compat_import(self):
        """device_detector からの再エクスポートが機能することを確認"""
        from src.core.device_detector import format_capacity as fc_compat

        assert fc_compat(1024**3) == "1.00 GB"
