"""TripleHashEngine の既知ベクトル検証"""
import hashlib
from pathlib import Path

from src.core.hash_engine import TripleHashEngine, verify_image_hash


class TestTripleHashEngine:
    def test_empty_input(self):
        engine = TripleHashEngine()
        digests = engine.hexdigests()
        assert digests["md5"] == hashlib.md5(b"").hexdigest()
        assert digests["sha1"] == hashlib.sha1(b"").hexdigest()
        assert digests["sha256"] == hashlib.sha256(b"").hexdigest()

    def test_known_vector_abc(self):
        engine = TripleHashEngine()
        engine.update(b"abc")
        digests = engine.hexdigests()
        assert digests["md5"] == "900150983cd24fb0d6963f7d28e17f72"
        assert digests["sha1"] == "a9993e364706816aba3e25717850c26c9cd0d89d"
        assert digests["sha256"] == (
            "ba7816bf8f01cfea414140de5dae2223"
            "b00361a396177a9cb410ff61f20015ad"
        )

    def test_incremental_update(self):
        data = b"The quick brown fox jumps over the lazy dog"

        engine_full = TripleHashEngine()
        engine_full.update(data)

        engine_split = TripleHashEngine()
        engine_split.update(data[:10])
        engine_split.update(data[10:25])
        engine_split.update(data[25:])

        assert engine_full.hexdigests() == engine_split.hexdigests()

    def test_bytes_processed(self):
        engine = TripleHashEngine()
        engine.update(b"x" * 1024)
        engine.update(b"y" * 2048)
        assert engine.bytes_processed == 3072

    def test_reset(self):
        engine = TripleHashEngine()
        engine.update(b"data")
        engine.reset()
        assert engine.bytes_processed == 0
        assert engine.hexdigests() == TripleHashEngine().hexdigests()

    def test_copy(self):
        engine = TripleHashEngine()
        engine.update(b"partial")
        copied = engine.copy()
        engine.update(b"_more")
        copied.update(b"_more")
        assert engine.hexdigests() == copied.hexdigests()


class TestVerifyImageHash:
    def test_matching_hash(self, tmp_path: Path):
        test_file = tmp_path / "test.img"
        test_data = b"forensic image data " * 100
        test_file.write_bytes(test_data)

        expected = {
            "md5": hashlib.md5(test_data).hexdigest(),
            "sha1": hashlib.sha1(test_data).hexdigest(),
            "sha256": hashlib.sha256(test_data).hexdigest(),
        }

        result = verify_image_hash(test_file, expected)
        assert result["all_match"] is True

    def test_mismatched_hash(self, tmp_path: Path):
        test_file = tmp_path / "test.img"
        test_file.write_bytes(b"actual data")

        expected = {
            "md5": "0" * 32,
            "sha1": "0" * 40,
            "sha256": "0" * 64,
        }

        result = verify_image_hash(test_file, expected)
        assert result["all_match"] is False
