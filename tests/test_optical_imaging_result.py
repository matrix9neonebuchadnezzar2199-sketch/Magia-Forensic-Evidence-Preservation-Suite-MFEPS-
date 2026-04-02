"""OpticalImagingResult (Phase 2-1)"""


class TestOpticalImagingResult:
    def test_defaults(self):
        from src.core.optical_engine import OpticalImagingResult

        r = OpticalImagingResult()
        assert r.status == "completed"
        assert r.error == ""
        assert r.source_hashes == {}
        assert r.copied_bytes == 0
        assert r.total_bytes == 0
        assert r.error_count == 0
        assert r.error_sectors == []
        assert r.elapsed_seconds == 0.0
        assert r.output_path == ""
        assert r.decrypt_method is None
        assert r.css_scrambled is None
        assert r.aacs_mkb_version is None

    def test_completed_shape(self):
        from src.core.optical_engine import OpticalImagingResult

        r = OpticalImagingResult(
            status="completed",
            source_hashes={"md5": "a", "sha256": "b"},
            copied_bytes=100,
            total_bytes=100,
            error_count=0,
            error_sectors=[],
            elapsed_seconds=1.5,
            output_path="/tmp/out.iso",
            decrypt_method="raw",
            css_scrambled=False,
            aacs_mkb_version=None,
        )
        assert r.status == "completed"
        assert r.source_hashes["md5"] == "a"
        assert r.copied_bytes == 100

    def test_failed_shape(self):
        from src.core.optical_engine import OpticalImagingResult

        r = OpticalImagingResult(
            status="failed",
            error="capacity zero",
            output_path="/x/out.iso",
        )
        assert r.status == "failed"
        assert r.error == "capacity zero"
        assert r.source_hashes == {}
