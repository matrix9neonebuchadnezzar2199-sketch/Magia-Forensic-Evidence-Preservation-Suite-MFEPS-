"""long_path ユーティリティ（Phase 4-1）"""
import os
import sys
from unittest.mock import patch

import pytest

from src.utils.long_path import (
    LONG_PATH_THRESHOLD,
    ensure_cli_path,
    ensure_long_path,
    shorten_component,
    validate_path_length,
)


class TestEnsureLongPath:
    def test_short_path_unchanged(self, tmp_path):
        p = tmp_path / "a" / "b.txt"
        s = ensure_long_path(p)
        assert not s.startswith("\\\\?\\")

    @pytest.mark.skipif(sys.platform != "win32", reason="Win32 長パスプレフィクス")
    def test_long_path_gets_extended_prefix(self, tmp_path):
        # 解決後の長さが閾値を超えるパス
        long_name = "x" * (LONG_PATH_THRESHOLD + 20)
        p = tmp_path / long_name
        s = ensure_long_path(p)
        assert s.startswith("\\\\?\\")
        assert "\\\\?\\UNC\\" not in s or tmp_path.as_posix().startswith("//")

    @pytest.mark.skipif(sys.platform != "win32", reason="UNC は Win32 前提")
    def test_unc_path_uses_unc_prefix(self):
        unc = "\\\\server\\share\\deep\\" + "x" * 250
        with patch("os.path.abspath", return_value=unc):
            with patch("os.path.normpath", side_effect=lambda x: x):
                s = ensure_long_path(unc)
        assert s.startswith("\\\\?\\UNC\\")

    def test_already_prefixed_not_doubled(self):
        prefixed = "\\\\?\\C:\\already\\long"
        assert ensure_long_path(prefixed) == prefixed

    def test_validate_path_length(self):
        assert validate_path_length("a" * 100) is True
        assert validate_path_length("a" * 40000) is False


class TestEnsureCliPath:
    @pytest.mark.skipif(sys.platform != "win32", reason="MAX_PATH セマンティクス")
    def test_cli_path_under_260_no_prefix_even_if_over_240(self, tmp_path):
        # 241–260 文字帯: ensure_long_path は付与するが CLI は付けない
        base = str(tmp_path.resolve())
        pad = max(0, 245 - len(base))
        mid = tmp_path / ("p" * pad)
        p = mid / "z.txt"
        n = os.path.normpath(os.path.abspath(str(p)))
        if not (LONG_PATH_THRESHOLD < len(n) <= 260):
            pytest.skip("一時パス長が 241–260 文字帯外")
        s_cli = ensure_cli_path(p)
        s_long = ensure_long_path(p)
        assert not s_cli.startswith("\\\\?\\")
        assert s_long.startswith("\\\\?\\")


class TestShortenComponent:
    def test_keeps_extension(self):
        assert shorten_component("a" * 250 + ".iso", max_len=30).endswith(".iso")
        assert len(shorten_component("x.bin", max_len=200)) == len("x.bin")
