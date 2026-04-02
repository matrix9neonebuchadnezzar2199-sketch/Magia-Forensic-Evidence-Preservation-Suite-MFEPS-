"""resolve_safe_output_path (Phase 2-5)"""
from unittest.mock import MagicMock, patch

from src.utils.output_path_helpers import resolve_safe_output_path


class TestOutputPathHelpers:
    def test_no_collision_returns_basename(self, tmp_path):
        d = tmp_path / "o"
        d.mkdir()
        p = resolve_safe_output_path(d, "image", ".dd")
        assert p == d / "image.dd"

    def test_collision_adds_timestamp(self, tmp_path):
        d = tmp_path / "o"
        d.mkdir()
        (d / "image.dd").write_bytes(b"x")
        p = resolve_safe_output_path(d, "image", ".dd")
        assert p != d / "image.dd"
        assert p.name.startswith("image_")
        assert p.suffix == ".dd"

    def test_timestamp_collision_adds_counter(self, tmp_path):
        d = tmp_path / "o"
        d.mkdir()
        (d / "image.dd").touch()
        ts = "20260101T000000Z"
        fake_now = MagicMock()
        fake_now.strftime.return_value = ts
        with patch("src.utils.output_path_helpers.datetime") as mod_dt:
            mod_dt.now.return_value = fake_now
            (d / f"image_{ts}.dd").touch()
            p = resolve_safe_output_path(d, "image", ".dd")
        assert p.name == f"image_{ts}_1.dd"

    def test_various_extensions(self, tmp_path):
        d = tmp_path / "o"
        d.mkdir()
        assert resolve_safe_output_path(d, "x", ".E01") == d / "x.E01"
        assert resolve_safe_output_path(d, "x", ".iso") == d / "x.iso"
