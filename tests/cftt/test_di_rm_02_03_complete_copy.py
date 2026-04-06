"""DI-RM-02: 全セクタ取得, DI-RM-03: ハッシュ独立検証"""
from __future__ import annotations

import filecmp
import hashlib

import pytest

from tests.cftt.cftt_engine_helpers import run_mocked_imaging

pytestmark = pytest.mark.cftt


class TestDIRM0203:
    @pytest.mark.asyncio
    async def test_output_matches_source_bitwise(self, reference_image, tmp_path):
        """出力ファイルがソースとバイト単位で一致（DI-RM-02/06）"""
        r = await run_mocked_imaging(
            tmp_path,
            reference_image["data"],
            str(reference_image["path"]),
            verify_after_copy=False,
        )
        assert r.output_path
        assert filecmp.cmp(
            reference_image["path"], r.output_path, shallow=False
        ), "output must match source bytes"

    @pytest.mark.asyncio
    async def test_hash_matches_independent_calculation(self, reference_image, tmp_path):
        """ImagingResult のハッシュが独立 hashlib 計算と一致（DI-RM-03）"""
        r = await run_mocked_imaging(
            tmp_path,
            reference_image["data"],
            str(reference_image["path"]),
        )
        src = reference_image["data"]
        assert r.source_hashes.get("sha256") == hashlib.sha256(src).hexdigest()
        assert r.source_hashes.get("md5") == hashlib.md5(src).hexdigest()
        assert r.source_hashes.get("sha1") == hashlib.sha1(src).hexdigest()

    @pytest.mark.asyncio
    async def test_all_hash_algorithms_verified(self, reference_image, tmp_path):
        """MD5, SHA-1, SHA-256 が結果に含まれる"""
        r = await run_mocked_imaging(
            tmp_path,
            reference_image["data"],
            str(reference_image["path"]),
        )
        assert "md5" in r.source_hashes
        assert "sha1" in r.source_hashes
        assert "sha256" in r.source_hashes
