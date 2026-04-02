"""Phase 3-4: verify_image_hash cancel_event"""
import threading

from src.core.hash_engine import verify_image_hash


class TestVerifyImageHashCancel:
    def test_no_cancel_runs_normally(self, tmp_path):
        p = tmp_path / "f.bin"
        p.write_bytes(b"abc")
        r = verify_image_hash(
            p,
            {"md5": "900150983cd24fb0d6963f7d28e17f72"},
            buffer_size=16,
            md5=True,
            sha1=False,
            sha256=False,
            sha512=False,
        )
        assert not r.get("cancelled")
        assert r["all_match"] is True

    def test_cancel_immediate(self, tmp_path):
        p = tmp_path / "f.bin"
        p.write_bytes(b"x" * 1_000_000)
        ev = threading.Event()
        ev.set()
        r = verify_image_hash(
            p,
            {"md5": "x"},
            buffer_size=4096,
            cancel_event=ev,
            md5=True,
            sha1=False,
            sha256=False,
            sha512=False,
        )
        assert r.get("cancelled") is True
        assert r["all_match"] is False

    def test_cancel_mid_read(self, tmp_path):
        p = tmp_path / "f.bin"
        p.write_bytes(b"y" * 50_000)
        ev = threading.Event()

        def cb(_p, _t):
            ev.set()

        r = verify_image_hash(
            p,
            {"md5": "x"},
            buffer_size=4096,
            progress_callback=cb,
            cancel_event=ev,
            md5=True,
            sha1=False,
            sha256=False,
            sha512=False,
        )
        assert r.get("cancelled") is True
