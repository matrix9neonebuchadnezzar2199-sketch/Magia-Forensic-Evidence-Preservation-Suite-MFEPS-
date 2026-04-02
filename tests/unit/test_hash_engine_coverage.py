"""hash_engine 追加カバレッジ"""
import hashlib
import threading

from src.core.hash_engine import TripleHashEngine, verify_image_hash


def test_sha512_enabled():
    e = TripleHashEngine(sha512=True)
    e.update(b"test")
    h = e.hexdigests()
    assert "sha512" in h
    assert len(h["sha512"]) == 128


def test_copy():
    e = TripleHashEngine(sha512=True)
    e.update(b"data1")
    c = e.copy()
    c.update(b"data2")
    assert e.bytes_processed == 5
    assert c.bytes_processed == 10
    assert e.hexdigests() != c.hexdigests()


def test_reset():
    e = TripleHashEngine()
    e.update(b"test")
    before = e.hexdigests()
    e.reset()
    assert e.bytes_processed == 0
    e.update(b"test")
    assert e.hexdigests() == before


def test_verify_cancel(tmp_path):
    f = tmp_path / "img.bin"
    f.write_bytes(b"\x00" * 4096)
    ev = threading.Event()
    ev.set()
    result = verify_image_hash(f, {"md5": "abc"}, cancel_event=ev)
    assert result["cancelled"] is True
    assert result["all_match"] is False


def test_verify_match(tmp_path):
    data = b"hello world" * 100
    f = tmp_path / "match.bin"
    f.write_bytes(data)
    expected = {
        "md5": hashlib.md5(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    result = verify_image_hash(f, expected, sha1=False)
    assert result["all_match"] is True
