"""e01_writer.py の追加カバレッジ"""
from unittest.mock import patch

from src.core.e01_writer import (
    E01Params,
    E01Result,
    E01VerifyResult,
    E01Writer,
    _sanitize_ewf_metadata,
)


def test_check_available_no_ewfacquire():
    with patch.object(E01Writer, "_resolve_ewfacquire_path", return_value=""):
        result = E01Writer.check_available()
        assert result["ewfacquire_available"] is False


def test_check_available_detail_diagnostics():
    detail = E01Writer.check_available_detail()
    assert "ewfacquire_available" in detail
    assert "diagnostics" in detail


def test_sanitize_metadata():
    assert _sanitize_ewf_metadata("test\x00value") == "testvalue"


def test_e01_params_defaults():
    p = E01Params(source_path=r"\\.\PhysicalDrive1", output_dir="./out")
    assert "deflate" in p.compression_method or p.compression_method == "deflate"
    assert p.compression_level == "fast"
    assert p.ewf_format == "encase6"


def test_e01_result_defaults():
    r = E01Result()
    assert r.success is False
    assert r.output_files == []


def test_e01_verify_result_defaults():
    r = E01VerifyResult()
    assert r.verified is False
    assert r.stored_hashes == {}
