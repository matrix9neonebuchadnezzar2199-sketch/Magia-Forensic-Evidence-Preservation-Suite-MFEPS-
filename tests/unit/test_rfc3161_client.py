"""RFC3161Client（Phase 5-2）"""
from unittest.mock import MagicMock, patch

import pytest

from src.utils.rfc3161_client import RFC3161Client, RFC3161Error


class TestRFC3161Client:
    @patch("src.utils.rfc3161_client.get_config")
    def test_disabled_apply_noop(self, mock_cfg):
        cfg = MagicMock()
        cfg.mfeps_rfc3161_enabled = False
        cfg.mfeps_rfc3161_tsa_url = "http://example.com"
        mock_cfg.return_value = cfg

        class HR:
            sha256 = "aa" * 32
            rfc3161_token = None
            rfc3161_tsa_url = ""

        hr = HR()
        RFC3161Client().apply_to_source_hash_record(hr)
        assert hr.rfc3161_token is None

    @patch("src.utils.rfc3161_client.get_config")
    def test_enabled_property(self, mock_cfg):
        cfg = MagicMock()
        cfg.mfeps_rfc3161_enabled = True
        cfg.mfeps_rfc3161_tsa_url = "http://example.com"
        mock_cfg.return_value = cfg
        assert RFC3161Client().enabled is True

    @patch("src.utils.rfc3161_client.get_config")
    @patch("rfc3161ng.RemoteTimestamper")
    def test_request_success(self, mock_ts_cls, mock_cfg):
        cfg = MagicMock()
        cfg.mfeps_rfc3161_enabled = True
        cfg.mfeps_rfc3161_tsa_url = "http://timestamp.test"
        mock_cfg.return_value = cfg
        mock_st = MagicMock()
        mock_st.timestamp.return_value = b"\x30\x80"
        mock_ts_cls.return_value = mock_st
        client = RFC3161Client()
        result = client.request_timestamp("aa" * 32, algo="sha256")
        assert isinstance(result, bytes)
        mock_st.timestamp.assert_called_once()

    @patch("src.utils.rfc3161_client.get_config")
    @patch("rfc3161ng.RemoteTimestamper")
    def test_request_network_error(self, mock_ts_cls, mock_cfg):
        cfg = MagicMock()
        cfg.mfeps_rfc3161_enabled = True
        cfg.mfeps_rfc3161_tsa_url = "http://timestamp.test"
        mock_cfg.return_value = cfg
        mock_ts_cls.side_effect = OSError("network down")
        client = RFC3161Client()
        with pytest.raises(RFC3161Error, match="TSA 接続失敗"):
            client.request_timestamp("bb" * 32)
