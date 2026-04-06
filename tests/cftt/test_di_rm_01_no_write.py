"""DI-RM-01: ツールはソースに書き込みを行わない"""
from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from tests.cftt.cftt_engine_helpers import run_mocked_imaging

pytestmark = pytest.mark.cftt


class TestDIRM01:
    @pytest.mark.asyncio
    async def test_source_unchanged_after_imaging(self, reference_image, tmp_path):
        """イメージング後にリファレンスファイルの SHA-256 が変化しないこと"""
        pre_hash = hashlib.sha256(reference_image["path"].read_bytes()).hexdigest()
        await run_mocked_imaging(
            tmp_path,
            reference_image["data"],
            str(reference_image["path"]),
        )
        post_hash = hashlib.sha256(reference_image["path"].read_bytes()).hexdigest()
        assert pre_hash == post_hash, "DI-RM-01 FAIL: source was modified"

    @pytest.mark.asyncio
    async def test_source_opened_via_readonly_path(self, reference_image, tmp_path):
        """open_device がソースパスで呼ばれること"""
        src = str(reference_image["path"])
        opened: list[str] = []

        def open_dev(path: str) -> int:
            opened.append(path)
            return 99

        data = reference_image["data"]
        du = MagicMock()
        du.free = 10**12

        def mock_read_sectors(handle, offset, length, buffer=None):
            del handle, buffer
            end = min(offset + length, len(data))
            chunk = data[offset:end]
            if len(chunk) < length:
                chunk += b"\x00" * (length - len(chunk))
            return chunk

        from src.core.imaging_engine import ImagingEngine, ImagingJobParams

        job = ImagingJobParams(
            job_id="j1",
            evidence_id="e1",
            case_id="c1",
            source_path=src,
            output_dir=str(tmp_path / "out"),
            verify_after_copy=False,
        )
        engine = ImagingEngine()
        with patch(
            "src.core.imaging_engine.open_device", side_effect=open_dev
        ), patch(
            "src.core.imaging_engine.get_disk_geometry",
            return_value={"bytes_per_sector": 512},
        ), patch(
            "src.core.imaging_engine.get_disk_length", return_value=len(data)
        ), patch(
            "src.core.imaging_engine.read_sectors", side_effect=mock_read_sectors
        ), patch(
            "src.core.imaging_engine.verify_write_block", return_value=True
        ), patch(
            "src.core.imaging_engine.psutil.disk_usage", return_value=du
        ), patch(
            "src.core.imaging_engine.SafeDeviceHandle"
        ) as msdh:
            msdh.return_value.value = 99
            msdh.return_value.close = MagicMock()
            await engine.execute(job)

        assert opened == [src]
