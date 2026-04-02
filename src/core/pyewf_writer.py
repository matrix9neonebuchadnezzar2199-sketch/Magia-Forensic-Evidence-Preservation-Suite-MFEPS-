"""
MFEPS v2.1.0 — pyewf フォールバック E01 ライター
ewfacquire.exe が不在の場合に、pyewf (libewf Python binding) で
E01 ファイルを直接生成する。
"""
import asyncio
import logging
import time
from pathlib import Path
from typing import Callable, Optional

from src.core.e01_writer import E01Params, E01Result
from src.core.hash_engine import TripleHashEngine
from src.utils.safe_handle import SafeDeviceHandle
from src.core.win32_raw_io import get_disk_length, open_device, read_sectors

logger = logging.getLogger("mfeps.pyewf_writer")


def is_pyewf_available() -> bool:
    """pyewf がインポート可能か確認。"""
    try:
        import pyewf  # noqa: F401
        return True
    except ImportError:
        return False


def get_pyewf_version() -> str:
    """pyewf のバージョン文字列。"""
    try:
        import pyewf
        return getattr(pyewf, "get_version", lambda: "")()
    except Exception:
        return ""


class PyEWFWriter:
    """
    pyewf を使用して E01 ファイルを生成する。
    ewfacquire subprocess が利用できない場合のフォールバック。
    """

    def __init__(self) -> None:
        self._cancel_requested = False
        self._progress_callback: Optional[Callable] = None
        self._current_progress: dict = {
            "status": "idle",
            "percent": 0.0,
            "acquired_bytes": 0,
            "total_bytes": 0,
            "speed_bytes": 0,
        }

    def set_progress_callback(self, callback: Callable) -> None:
        self._progress_callback = callback

    def get_progress(self) -> dict:
        return dict(self._current_progress)

    async def cancel(self) -> None:
        self._cancel_requested = True

    async def acquire(self, params: E01Params) -> E01Result:
        """pyewf を使用してデバイスから E01 イメージを取得。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._acquire_sync, params)

    def _acquire_sync(self, params: E01Params) -> E01Result:
        """同期版 E01 取得。"""
        result = E01Result()

        try:
            import pyewf
        except ImportError:
            result.error_code = "E7001"
            result.error_message = (
                "pyewf がインストールされていません: "
                "pip install pyewf"
            )
            return result

        if self._cancel_requested:
            result.error_code = "E3006"
            result.error_message = "ユーザーによりキャンセルされました"
            return result

        dev: Optional[SafeDeviceHandle] = None
        ewf_handle = None
        start_time = time.monotonic()

        try:
            dev = SafeDeviceHandle(
                open_device(params.source_path), params.source_path
            )
            total_bytes = get_disk_length(dev.value)

            output_dir = Path(params.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_base = str(output_dir / params.output_basename)

            ewf_handle = pyewf.handle()
            ewf_handle.open(
                [f"{output_base}.E01"],
                "w",
            )

            if hasattr(ewf_handle, "set_media_size"):
                ewf_handle.set_media_size(total_bytes)
            elif hasattr(ewf_handle, "set_media_values"):
                try:
                    ewf_handle.set_media_values(total_bytes, 512, 0)
                except Exception:
                    logger.debug("set_media_values スキップ", exc_info=True)

            _set_meta = getattr(ewf_handle, "set_header_value", None)
            if callable(_set_meta):
                if params.case_number:
                    _set_meta("case_number", params.case_number)
                if params.evidence_number:
                    _set_meta("evidence_number", params.evidence_number)
                if params.examiner_name:
                    _set_meta("examiner_name", params.examiner_name)
                if params.description:
                    _set_meta("description", params.description)

            hash_engine = TripleHashEngine(
                md5=True, sha1=True, sha256=True, sha512=False,
            )

            buffer_size = 1_048_576
            offset = 0
            sector_size = 512

            while offset < total_bytes:
                if self._cancel_requested:
                    result.error_code = "E3006"
                    result.error_message = "ユーザーによりキャンセルされました"
                    break

                remaining = total_bytes - offset
                read_size = min(buffer_size, remaining)
                read_size = (read_size // sector_size) * sector_size
                if read_size == 0 and remaining > 0:
                    read_size = (
                        (remaining + sector_size - 1) // sector_size
                    ) * sector_size

                data = read_sectors(dev.value, offset, read_size)
                if len(data) < read_size:
                    data += b"\x00" * (read_size - len(data))
                chunk = data[:remaining]
                ewf_handle.write(chunk)
                hash_engine.update(chunk)
                offset += len(chunk)

                pct = (offset / total_bytes * 100) if total_bytes > 0 else 0
                self._current_progress.update({
                    "status": "imaging",
                    "percent": round(pct, 1),
                    "acquired_bytes": offset,
                    "total_bytes": total_bytes,
                    "speed_bytes": 0,
                })
                if self._progress_callback:
                    self._progress_callback(dict(self._current_progress))

            if ewf_handle is not None:
                ewf_handle.close()
                ewf_handle = None

            if not self._cancel_requested:
                elapsed = time.monotonic() - start_time
                hashes = hash_engine.hexdigests()
                result.success = True
                result.md5 = hashes.get("md5", "")
                result.sha256 = hashes.get("sha256", "")
                result.total_bytes = total_bytes
                result.acquired_bytes = offset
                result.elapsed_seconds = round(elapsed, 2)
                result.ewfacquire_version = f"pyewf {get_pyewf_version()}"
                result.command_line = f"[pyewf fallback] {params.source_path}"
                result.ewfacquire_return_code = 0

                result.output_files = sorted(
                    str(p) for p in output_dir.glob(
                        f"{params.output_basename}.E*"
                    )
                )
                result.segment_count = len(result.output_files)

                logger.info(
                    "pyewf E01 取得成功: %d segments, %s bytes",
                    result.segment_count,
                    f"{result.acquired_bytes:,}",
                )

        except OSError as e:
            result.error_code = "E7002"
            result.error_message = f"pyewf I/O エラー: {e}"
            logger.error(result.error_message, exc_info=True)
        except Exception as e:
            result.error_code = "E7002"
            result.error_message = f"pyewf 例外: {e}"
            logger.error(result.error_message, exc_info=True)
        finally:
            if ewf_handle is not None:
                try:
                    ewf_handle.close()
                except Exception:
                    pass
            if dev is not None:
                dev.close()

        result.elapsed_seconds = round(time.monotonic() - start_time, 2)
        return result
