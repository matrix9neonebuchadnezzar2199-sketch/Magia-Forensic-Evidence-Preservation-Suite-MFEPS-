"""DI-RM-06: ビット正確コピー, DI-RM-07: 検証成功"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core.hash_engine import verify_image_hash

from tests.cftt.cftt_engine_helpers import run_mocked_imaging

pytestmark = pytest.mark.cftt


class TestDIRM0607:
    @pytest.mark.asyncio
    async def test_verify_image_hash_all_match(self, reference_image, tmp_path):
        """verify_image_hash が all_match=True（DI-RM-07）"""
        r = await run_mocked_imaging(
            tmp_path,
            reference_image["data"],
            str(reference_image["path"]),
            verify_after_copy=True,
        )
        assert r.match_result == "matched"
        assert r.verify_hashes is not None

    @pytest.mark.asyncio
    async def test_tampered_image_detected(self, reference_image, tmp_path):
        """1バイト改ざんイメージで検証が不一致"""
        r = await run_mocked_imaging(
            tmp_path,
            reference_image["data"],
            str(reference_image["path"]),
            verify_after_copy=False,
        )
        outp = Path(r.output_path)
        blob = bytearray(outp.read_bytes())
        blob[0] ^= 0xFF
        outp.write_bytes(bytes(blob))
        vr = verify_image_hash(
            str(outp),
            r.source_hashes,
        )
        assert vr["all_match"] is False

    @pytest.mark.asyncio
    async def test_byte_count_exact(self, reference_image, tmp_path):
        """copied_bytes == total_bytes == reference_size"""
        r = await run_mocked_imaging(
            tmp_path,
            reference_image["data"],
            str(reference_image["path"]),
        )
        n = len(reference_image["data"])
        assert r.total_bytes == n
        assert r.copied_bytes == n
