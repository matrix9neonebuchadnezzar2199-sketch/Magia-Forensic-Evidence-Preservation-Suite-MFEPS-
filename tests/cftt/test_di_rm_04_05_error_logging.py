"""DI-RM-04/05: エラーセクタのログ記録と文書化"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.cftt.cftt_engine_helpers import SECTOR_SIZE, run_mocked_imaging

pytestmark = pytest.mark.cftt


class TestDIRM0405:
    @pytest.mark.asyncio
    async def test_error_sectors_recorded(self, reference_with_bad_sectors, tmp_path):
        """不良セクタが error_map.json に記録される（DI-RM-04）"""
        ref = reference_with_bad_sectors
        bad = {s * SECTOR_SIZE for s in ref["bad_sectors"]}
        r = await run_mocked_imaging(
            tmp_path,
            ref["data"],
            str(ref["path"]),
            buffer_size=SECTOR_SIZE,
            verify_after_copy=False,
            bad_byte_offsets=bad,
        )
        err_path = Path(r.output_path).parent / "error_map.json"
        assert err_path.is_file()
        payload = json.loads(err_path.read_text(encoding="utf-8"))
        assert payload.get("error_count", 0) >= 1
        assert len(payload.get("error_sectors", [])) >= 1

    @pytest.mark.asyncio
    async def test_error_count_matches(self, reference_with_bad_sectors, tmp_path):
        """error_map のセクタ数が注入数と一致（DI-RM-05）"""
        ref = reference_with_bad_sectors
        bad = {s * SECTOR_SIZE for s in ref["bad_sectors"]}
        r = await run_mocked_imaging(
            tmp_path,
            ref["data"],
            str(ref["path"]),
            buffer_size=SECTOR_SIZE,
            verify_after_copy=False,
            bad_byte_offsets=bad,
        )
        err_path = Path(r.output_path).parent / "error_map.json"
        data = json.loads(err_path.read_text(encoding="utf-8"))
        assert data["error_count"] == len(ref["bad_sectors"])
        assert set(data["error_sectors"]) == set(ref["bad_sectors"])

    @pytest.mark.asyncio
    async def test_zero_fill_on_error(self, reference_with_bad_sectors, tmp_path):
        """不良セクタがゼロ埋めされてイメージサイズが完了する"""
        ref = reference_with_bad_sectors
        bad = {s * SECTOR_SIZE for s in ref["bad_sectors"]}
        r = await run_mocked_imaging(
            tmp_path,
            ref["data"],
            str(ref["path"]),
            buffer_size=SECTOR_SIZE,
            verify_after_copy=False,
            bad_byte_offsets=bad,
        )
        assert r.status == "completed"
        assert Path(r.output_path).stat().st_size == len(ref["data"])
