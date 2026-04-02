"""rfc3161_client 分岐カバレッジ"""
import types
from unittest.mock import MagicMock, patch

import pytest

from src.utils.rfc3161_client import RFC3161Client, RFC3161Error


def _cfg(enabled: bool = True, url: str = "http://tsa.example/tsa"):
    m = MagicMock()
    m.mfeps_rfc3161_enabled = enabled
    m.mfeps_rfc3161_tsa_url = url
    return m


def test_request_timestamp_disabled():
    with patch("src.utils.rfc3161_client.get_config", return_value=_cfg(False)):
        c = RFC3161Client()
        assert c.enabled is False
        with pytest.raises(RFC3161Error, match="無効"):
            c.request_timestamp("a" * 64)


def test_request_timestamp_no_url():
    with patch("src.utils.rfc3161_client.get_config", return_value=_cfg(True, "")):
        c = RFC3161Client()
        with pytest.raises(RFC3161Error, match="TSA URL"):
            c.request_timestamp("a" * 64)


def test_request_timestamp_bad_hex_len():
    with patch("src.utils.rfc3161_client.get_config", return_value=_cfg(True)):
        c = RFC3161Client()
        with pytest.raises(RFC3161Error, match="不正"):
            c.request_timestamp("abc")


def test_request_timestamp_bad_hex_value():
    with patch("src.utils.rfc3161_client.get_config", return_value=_cfg(True)):
        c = RFC3161Client()
        with pytest.raises(RFC3161Error, match="解析"):
            c.request_timestamp("zz" * 16)


def test_request_timestamp_success():
    class FakeStamper:
        def timestamp(self, digest):
            return b"\x01\x02"

    fake_mod = types.SimpleNamespace(
        RemoteTimestamper=lambda *a, **k: FakeStamper()
    )
    with patch("src.utils.rfc3161_client.get_config", return_value=_cfg(True)):
        c = RFC3161Client()
        with patch.dict("sys.modules", {"rfc3161ng": fake_mod}):
            tok = c.request_timestamp("ab" * 16)
        assert tok == b"\x01\x02"


def test_apply_to_source_skips_when_no_sha():
    hr = MagicMock()
    hr.sha256 = ""
    with patch("src.utils.rfc3161_client.get_config", return_value=_cfg(True)):
        c = RFC3161Client()
        c.apply_to_source_hash_record(hr)


def test_apply_to_source_skips_when_disabled():
    hr = MagicMock()
    hr.sha256 = "ab" * 16
    with patch("src.utils.rfc3161_client.get_config", return_value=_cfg(False)):
        c = RFC3161Client()
        c.apply_to_source_hash_record(hr)


def test_request_timestamp_tsa_raises_wrapped():
    class BoomStamper:
        def timestamp(self, digest):
            raise ConnectionError("network down")

    fake_mod = types.SimpleNamespace(
        RemoteTimestamper=lambda *a, **k: BoomStamper()
    )
    with patch("src.utils.rfc3161_client.get_config", return_value=_cfg(True)):
        c = RFC3161Client()
        with patch.dict("sys.modules", {"rfc3161ng": fake_mod}):
            with pytest.raises(RFC3161Error, match="TSA"):
                c.request_timestamp("ab" * 16)


def test_request_timestamp_empty_token():
    class EmptyStamper:
        def timestamp(self, digest):
            return None

    fake_mod = types.SimpleNamespace(
        RemoteTimestamper=lambda *a, **k: EmptyStamper()
    )
    with patch("src.utils.rfc3161_client.get_config", return_value=_cfg(True)):
        c = RFC3161Client()
        with patch.dict("sys.modules", {"rfc3161ng": fake_mod}):
            with pytest.raises(RFC3161Error, match="空"):
                c.request_timestamp("ab" * 16)


def test_apply_to_source_logs_rfc3161_error():
    hr = MagicMock()
    hr.sha256 = "ab" * 16
    with patch("src.utils.rfc3161_client.get_config", return_value=_cfg(True)):
        c = RFC3161Client()
        with patch.object(c, "request_timestamp", side_effect=RFC3161Error("x")):
            c.apply_to_source_hash_record(hr)
