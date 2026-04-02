"""
MFEPS — 異常系テスト（Sprint A-2）
中止・容量不足・権限なし・ewfacquire 未設定/異常終了・読取エラー
"""
import asyncio
import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.device_detector import DeviceInfo
from src.core.e01_writer import E01Params, E01Writer
from src.core.imaging_engine import ImagingEngine, ImagingJobParams
from src.models.database import get_session, init_database
from src.models.schema import Case, EvidenceItem
from src.services.imaging_service import ImagingService


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────


@pytest.fixture
def neg_db(tmp_path):
    """テスト用 DB を tmp_path に初期化し、基本レコードを作成"""
    init_database(tmp_path / "neg_test.db")
    session = get_session()
    case = Case(case_number="NEG-001", case_name="Negative Test")
    session.add(case)
    session.commit()
    ev = EvidenceItem(
        case_id=case.id,
        evidence_number="EV-NEG",
        media_type="usb_hdd",
    )
    session.add(ev)
    session.commit()
    session.close()
    return {"case_id": case.id, "evidence_id": ev.id, "tmp_path": tmp_path}


def _mock_config(tmp_path: Path) -> MagicMock:
    m = MagicMock()
    m.output_dir = tmp_path / "out"
    m.mfeps_buffer_size = 1_048_576
    m.e01_segment_size_bytes = 1_500_000_000
    m.e01_compression_method = "deflate"
    m.e01_compression_level = "fast"
    m.e01_ewf_format = "encase6"
    return m


# ──────────────────────────────────────────────
# 1. RAW キャンセル（E3006）
# ──────────────────────────────────────────────


class TestRawCancel:
    def test_cancel_sets_event(self):
        """cancel() 呼び出し後に _cancel_event がセットされること"""
        engine = ImagingEngine(buffer_size=512)

        async def _run():
            await engine.cancel()

        asyncio.run(_run())
        assert engine._cancel_event.is_set()

    def test_cancel_event_stops_buffer_manager(self):
        """cancel_event がセット済みなら process_loop は 0 バイトで終了"""
        from src.core.buffer_manager import DoubleBufferManager
        from src.core.hash_engine import TripleHashEngine

        def fake_read(_offset, size, _buf):
            return b"\x00" * size

        mgr = DoubleBufferManager(buffer_size=512, sector_size=512)
        h = TripleHashEngine(md5=True, sha1=False, sha256=False)
        out = io.BytesIO()
        cancel = asyncio.Event()
        pause = asyncio.Event()
        pause.set()
        cancel.set()

        async def run():
            rt = asyncio.create_task(
                mgr.read_loop(fake_read, 10_000, cancel, pause)
            )
            processed = await mgr.process_loop(h, out)
            await rt
            return processed

        assert asyncio.run(run()) == 0


# ──────────────────────────────────────────────
# 2. E01 キャンセル（E3006）
# ──────────────────────────────────────────────


class TestE01Cancel:
    def test_cancel_sets_flag(self):
        writer = E01Writer()

        async def _run():
            await writer.cancel()

        asyncio.run(_run())
        assert writer._cancel_requested is True

    def test_acquire_returns_e3006_when_cancel_during_read(self):
        """ストリーム読取中にキャンセルすると E3006"""
        writer = E01Writer()

        async def mark_cancel(*_a, **_kw):
            writer._cancel_requested = True

        avail = {
            "ewfacquire_available": True,
            "ewfverify_available": False,
            "ewfacquire_path": "ewfacquire.exe",
            "ewfverify_path": "",
            "ewfacquire_version": "20230405",
            "ewfverify_version": "",
        }

        mock_proc = AsyncMock()
        mock_proc.stdout = AsyncMock()
        mock_proc.stderr = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = 0

        with patch.object(E01Writer, "check_available", return_value=avail), patch.object(
            E01Writer, "_resolve_ewfacquire_path", return_value="ewfacquire.exe"
        ), patch("asyncio.create_subprocess_exec", return_value=mock_proc), patch.object(
            writer, "_read_stream_cr_aware", side_effect=mark_cancel
        ):
            params = E01Params(
                source_path=r"\\.\PhysicalDrive99",
                output_dir="/tmp/test_e01",
            )
            result = asyncio.run(writer.acquire(params))

        assert result.error_code == "E3006"
        assert "キャンセル" in result.error_message


# ──────────────────────────────────────────────
# 3. ディスク容量不足（E1004）
# ──────────────────────────────────────────────


class TestDiskFull:
    def test_insufficient_space_returns_e1004(self):
        engine = ImagingEngine(buffer_size=512)
        params = ImagingJobParams(
            job_id="diskfull-001",
            evidence_id="ev-001",
            case_id="case-001",
            source_path=r"\\.\PhysicalDrive99",
            output_dir="/tmp/output",
        )

        mock_usage = MagicMock()
        mock_usage.free = 100

        with patch("src.core.imaging_engine.open_device", return_value=999), patch(
            "src.core.imaging_engine.get_disk_geometry",
            return_value={"bytes_per_sector": 512},
        ), patch(
            "src.core.imaging_engine.get_disk_length", return_value=1_000_000_000
        ), patch(
            "src.utils.safe_handle.close_device"
        ), patch(
            "src.core.imaging_engine.verify_write_block", return_value=True
        ), patch(
            "psutil.disk_usage", return_value=mock_usage
        ), patch(
            "pathlib.Path.mkdir"
        ):
            result = asyncio.run(engine.execute(params))

        assert result.status == "failed"
        assert result.error_code == "E1004"
        assert "容量" in (result.error_message or "")


# ──────────────────────────────────────────────
# 4. 管理者権限なし / デバイスアクセス拒否
# ──────────────────────────────────────────────


class TestPermissionDenied:
    def test_open_device_permission_error(self):
        engine = ImagingEngine(buffer_size=512)
        params = ImagingJobParams(
            job_id="perm-001",
            evidence_id="ev-001",
            case_id="case-001",
            source_path=r"\\.\PhysicalDrive99",
            output_dir="/tmp/output",
        )

        with patch(
            "src.core.imaging_engine.open_device",
            side_effect=PermissionError("アクセスが拒否されました"),
        ):
            result = asyncio.run(engine.execute(params))

        assert result.status == "failed"
        assert "アクセス" in (result.error_message or "") or "Permission" in (
            result.error_message or ""
        )


# ──────────────────────────────────────────────
# 5. ewfacquire 未設定（E7001）
# ──────────────────────────────────────────────


class TestEwfacquireNotAvailable:
    def test_acquire_returns_e7001_when_not_found(self):
        writer = E01Writer()

        with patch.object(
            E01Writer,
            "check_available",
            return_value={
                "ewfacquire_available": False,
                "ewfverify_available": False,
                "ewfacquire_path": "",
                "ewfverify_path": "",
                "ewfacquire_version": "",
                "ewfverify_version": "",
            },
        ), patch.object(E01Writer, "_resolve_ewfacquire_path", return_value=""):
            params = E01Params(
                source_path=r"\\.\PhysicalDrive1",
                output_dir="/tmp/test",
            )
            result = asyncio.run(writer.acquire(params))

        assert result.success is False
        assert result.error_code == "E7001"
        assert "ewfacquire" in result.error_message

    def test_start_imaging_raises_when_e01_unavailable(self, neg_db):
        """ImagingService.start_imaging が E01 未設定時に RuntimeError"""
        svc = ImagingService()
        device = DeviceInfo(
            device_path=r"\\.\PhysicalDrive99",
            model="Test Device",
            serial="SN123",
            capacity_bytes=1_000_000,
            interface_type="USB",
            media_type="Removable",
        )

        with patch.object(
            E01Writer,
            "check_available",
            return_value={
                "ewfacquire_available": False,
                "ewfverify_available": False,
                "ewfacquire_path": "",
                "ewfverify_path": "",
                "ewfacquire_version": "",
                "ewfverify_version": "",
            },
        ), patch(
            "src.services.imaging_service.check_write_protection",
            return_value={
                "hardware_blocked": False,
                "registry_blocked": False,
                "is_protected": False,
            },
        ), patch(
            "src.services.imaging_service.get_config",
            return_value=_mock_config(neg_db["tmp_path"]),
        ), pytest.raises(RuntimeError, match="ewfacquire"):
            asyncio.run(
                svc.start_imaging(
                    device,
                    "NEG-001",
                    "EV-NEG",
                    output_format="e01",
                )
            )


# ──────────────────────────────────────────────
# 6. ewfacquire 異常終了（E7002）
# ──────────────────────────────────────────────


class TestEwfacquireFailure:
    def test_acquire_returns_e7002_on_nonzero_exit(self):
        writer = E01Writer()
        avail = {
            "ewfacquire_available": True,
            "ewfverify_available": False,
            "ewfacquire_path": "ewfacquire.exe",
            "ewfverify_path": "",
            "ewfacquire_version": "20230405",
            "ewfverify_version": "",
        }
        mock_proc = AsyncMock()
        mock_proc.stdout = AsyncMock()
        mock_proc.stderr = AsyncMock()
        mock_proc.wait = AsyncMock(return_value=1)
        mock_proc.returncode = 1

        async def noop_read(*_a, **_kw):
            pass

        with patch.object(E01Writer, "check_available", return_value=avail), patch.object(
            E01Writer, "_resolve_ewfacquire_path", return_value="ewfacquire.exe"
        ), patch("asyncio.create_subprocess_exec", return_value=mock_proc), patch.object(
            writer, "_read_stream_cr_aware", side_effect=noop_read
        ):
            params = E01Params(
                source_path=r"\\.\PhysicalDrive1",
                output_dir="/tmp/e01_fail",
            )
            result = asyncio.run(writer.acquire(params))

        assert result.error_code == "E7002"


# ──────────────────────────────────────────────
# 7. 読取エラー（OSError）→ error_count
# ──────────────────────────────────────────────


class TestReadOSError:
    def test_read_error_increments_error_count(self, tmp_path):
        out_dir = tmp_path / "readerr"
        out_dir.mkdir(parents=True)
        engine = ImagingEngine(buffer_size=512)
        params = ImagingJobParams(
            job_id="read-err-001",
            evidence_id="ev-001",
            case_id="case-001",
            source_path=r"\\.\PhysicalDrive99",
            output_dir=str(out_dir),
            verify_after_copy=False,
        )

        mock_usage = MagicMock()
        mock_usage.free = 10_000_000_000

        calls = [0]

        def flaky_read(_handle, _offset, size, buffer=None):
            calls[0] += 1
            if calls[0] >= 2:
                raise OSError(111, "fake media error")
            return b"\x00" * min(size, 512)

        with patch("src.core.imaging_engine.open_device", return_value=999), patch(
            "src.core.imaging_engine.get_disk_geometry",
            return_value={"bytes_per_sector": 512},
        ), patch("src.core.imaging_engine.get_disk_length", return_value=4096), patch(
            "src.utils.safe_handle.close_device"
        ), patch(
            "src.core.imaging_engine.verify_write_block", return_value=True
        ), patch("psutil.disk_usage", return_value=mock_usage), patch(
            "src.core.imaging_engine.read_sectors", side_effect=flaky_read
        ):
            result = asyncio.run(engine.execute(params))

        assert result.error_count > 0
        assert len(result.error_sectors) > 0
