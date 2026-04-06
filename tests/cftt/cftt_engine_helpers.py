"""CFTT 用 ImagingEngine モック実行ヘルパ"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.core.imaging_engine import ImagingEngine, ImagingJobParams, ImagingResult

SECTOR_SIZE = 512


async def run_mocked_imaging(
    tmp_path,
    data: bytes,
    source_path: str,
    *,
    buffer_size: int = 1_048_576,
    verify_after_copy: bool = True,
    bad_byte_offsets: set[int] | None = None,
) -> ImagingResult:
    du = MagicMock()
    du.free = max(len(data), 1024) * 100

    def mock_read_sectors(handle, offset, length, buffer=None):
        del handle, buffer
        if bad_byte_offsets:
            for bo in bad_byte_offsets:
                if offset <= bo < offset + length:
                    raise OSError(f"CRC error at offset {bo}")
        end = min(offset + length, len(data))
        chunk = data[offset:end]
        if len(chunk) < length:
            chunk += b"\x00" * (length - len(chunk))
        return chunk

    job = ImagingJobParams(
        job_id="cftt-j1",
        evidence_id="e1",
        case_id="c1",
        source_path=source_path,
        output_dir=str(tmp_path / "out"),
        buffer_size=buffer_size,
        verify_after_copy=verify_after_copy,
    )
    engine = ImagingEngine(buffer_size=job.buffer_size)
    with patch("src.core.imaging_engine.open_device", return_value=99), patch(
        "src.core.imaging_engine.get_disk_geometry",
        return_value={"bytes_per_sector": SECTOR_SIZE},
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
        return await engine.execute(job)
