"""
MFEPS v2.1.0 — Pure-Python ブロックデバイス イメージングエンジン
ctypes Win32 API 経由 RAW セクタ読取 + ダブルバッファ + トリプルハッシュ
"""
import asyncio
import json
import logging
import os
import threading
import time

import psutil
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel, Field

from src.core.buffer_manager import DoubleBufferManager
from src.core.hash_engine import TripleHashEngine, verify_image_hash
from src.core.win32_raw_io import (
    open_device,
    get_disk_geometry,
    get_disk_length,
    read_sectors,
)
from src.core.write_blocker import verify_write_block
from src.utils.incomplete_file_detector import detect_incomplete_files
from src.utils.long_path import maybe_extend_path
from src.utils.output_path_helpers import resolve_safe_output_path
from src.utils.safe_handle import SafeDeviceHandle, SafeFileHandle

logger = logging.getLogger("mfeps.imaging_engine")


class ImagingJobParams(BaseModel):
    """イメージングジョブパラメータ"""
    job_id: str
    evidence_id: str
    case_id: str
    source_path: str           # \\.\PhysicalDrive1
    output_dir: str            # ./output/case001/ev001/
    output_format: str = "raw"
    buffer_size: int = 1_048_576
    retry_count: int = 3
    verify_after_copy: bool = True
    hash_md5: bool = True
    hash_sha1: bool = True
    hash_sha256: bool = True
    hash_sha512: bool = False
    # UI 表示用（E01 メタデータ等）。case_id / evidence_id は UUID
    case_number_str: str = ""
    evidence_number_str: str = ""


class ImagingResult(BaseModel):
    """イメージング結果"""
    job_id: str
    status: str = "completed"            # completed / failed / cancelled
    source_hashes: dict = Field(default_factory=dict)  # {md5, sha1?, sha256, ...}
    verify_hashes: Optional[dict] = None
    match_result: str = "pending"        # matched / mismatched / pending
    total_bytes: int = 0
    copied_bytes: int = 0
    error_count: int = 0
    error_sectors: list[int] = []
    elapsed_seconds: float = 0.0
    avg_speed_mibps: float = 0.0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    output_path: str = ""
    incomplete_files: list[str] = Field(default_factory=list)
    incomplete_total_bytes: int = 0
    incomplete_file_records: list[dict] = Field(default_factory=list)


class ImagingEngine:
    """
    Pure-Python ブロックデバイスイメージングエンジン。
    ダブルバッファリング + トリプルハッシュ同時計算で高速コピー。
    """

    def __init__(self, buffer_size: int = 1_048_576):
        self.buffer_size = buffer_size
        self._cancel_event = asyncio.Event()
        self._verify_thread_cancel = threading.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初期: 実行中（非ポーズ）
        self._progress: dict = {
            "copied_bytes": 0,
            "total_bytes": 0,
            "speed_mibps": 0.0,
            "eta_seconds": 0.0,
            "error_count": 0,
            "status": "idle",
        }
        self._progress_callback: Optional[Callable] = None

    async def execute(self, job: ImagingJobParams) -> ImagingResult:
        """メインイメージングフロー"""
        start_time = time.time()
        dev: SafeDeviceHandle | None = None
        sfh: SafeFileHandle | None = None
        buffer_mgr: DoubleBufferManager | None = None
        result = ImagingResult(job_id=job.job_id)
        self._verify_thread_cancel.clear()

        try:
            self._progress["status"] = "starting"
            logger.info(f"イメージング開始: {job.source_path}")

            # 1. ソースデバイスオープン → ジオメトリ → 長さ
            try:
                dev = SafeDeviceHandle(
                    open_device(job.source_path), job.source_path
                )
            except OSError as e:
                result.status = "failed"
                result.error_code = "E2005"
                result.error_message = str(e)
                logger.error("デバイスオープン失敗: %s", e, exc_info=True)
                return result

            try:
                geometry = get_disk_geometry(dev.value)
            except OSError as e:
                result.status = "failed"
                result.error_code = "E2006"
                result.error_message = str(e)
                logger.error("ジオメトリ取得失敗: %s", e, exc_info=True)
                return result

            try:
                total_bytes = get_disk_length(dev.value)
            except OSError as e:
                result.status = "failed"
                result.error_code = "E2006"
                result.error_message = str(e)
                logger.error("ディスク長取得失敗: %s", e, exc_info=True)
                return result

            sector_size = geometry["bytes_per_sector"]

            result.total_bytes = total_bytes
            self._progress["total_bytes"] = total_bytes
            logger.info(
                f"ソース: {total_bytes} bytes ({total_bytes / (1024**3):.2f} GiB), "
                f"sector_size={sector_size}")

            # 2. ライトブロック検証
            logger.info("ライトブロック検証中...")
            wb_ok = verify_write_block(job.source_path)
            if not wb_ok:
                logger.warning("⚠️ ライトブロック未検証 — 続行します")

            # 3. 出力ファイル作成
            output_dir = maybe_extend_path(Path(job.output_dir))
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = resolve_safe_output_path(output_dir, "image", ".dd")
            result.output_path = str(output_path)

            # 出力先容量チェック
            disk_usage = psutil.disk_usage(str(output_dir))
            if disk_usage.free < total_bytes * 1.01:
                result.status = "failed"
                result.error_code = "E1004"
                result.error_message = (
                    f"出力先容量不足: 必要 {total_bytes / (1024**3):.1f} GiB, "
                    f"空き {disk_usage.free / (1024**3):.1f} GiB")
                logger.error(result.error_message)
                return result

            sfh = SafeFileHandle(open(output_path, "wb"))

            # 4. イメージングパイプライン
            self._progress["status"] = "imaging"
            buffer_mgr = DoubleBufferManager(
                buffer_size=job.buffer_size, sector_size=sector_size
            )
            hash_engine = TripleHashEngine(
                md5=job.hash_md5,
                sha1=job.hash_sha1,
                sha256=job.hash_sha256,
                sha512=job.hash_sha512,
            )

            # 読取（事前確保バッファで Win32 読取の割り当てを抑止）
            def _read(offset: int, size: int, buf) -> bytes:
                return read_sectors(dev.value, offset, size, buffer=buf)

            # 進捗更新関数
            speed_samples = []
            last_time = time.time()
            last_bytes = 0

            def _progress(copied: int):
                nonlocal last_time, last_bytes
                now = time.time()
                dt = now - last_time

                if dt >= 0.5:
                    speed = (copied - last_bytes) / dt / (1024 * 1024)
                    speed_samples.append(speed)
                    if len(speed_samples) > 10:
                        speed_samples.pop(0)
                    avg_speed = sum(speed_samples) / len(speed_samples)

                    remaining = total_bytes - copied
                    eta = remaining / (avg_speed * 1024 * 1024) if avg_speed > 0 else 0

                    self._progress.update({
                        "copied_bytes": copied,
                        "speed_mibps": round(avg_speed, 1),
                        "eta_seconds": round(eta, 0),
                        "error_count": buffer_mgr.error_count,
                    })

                    last_time = now
                    last_bytes = copied

                if self._progress_callback:
                    self._progress_callback(self._progress)

            # read_loop + process_loop を並列実行
            read_task = asyncio.create_task(
                buffer_mgr.read_loop(
                    _read, total_bytes,
                    self._cancel_event, self._pause_event))

            process_task = asyncio.create_task(
                buffer_mgr.process_loop(hash_engine, sfh.raw, _progress))

            await asyncio.gather(read_task, process_task)

            # 5. フラッシュ・クローズ（検証前にデバイス・出力ファイルを解放）
            sfh.flush()
            os.fsync(sfh.raw.fileno())
            sfh.close()
            sfh = None
            dev.close()
            dev = None

            # 6. ソースハッシュ確定
            result.source_hashes = hash_engine.hexdigests()
            result.copied_bytes = hash_engine.bytes_processed
            result.error_count = buffer_mgr.error_count
            result.error_sectors = buffer_mgr.error_sectors

            logger.info(f"コピー完了: {result.copied_bytes} bytes, "
                        f"エラーセクタ: {result.error_count}")
            for algo, label in (
                ("md5", "MD5"), ("sha1", "SHA1"),
                ("sha256", "SHA256"), ("sha512", "SHA512"),
            ):
                if algo in result.source_hashes:
                    logger.info(f"ソースハッシュ {label}={result.source_hashes[algo]}")

            # 7. イメージ検証（キャンセル時は検証をスキップ）
            if self._cancel_event.is_set():
                result.status = "cancelled"
                result.error_code = "E3006"
                result.error_message = "ユーザーによりキャンセルされました"
            elif job.verify_after_copy:
                self._progress["status"] = "verifying"
                logger.info("イメージ検証（再ハッシュ）開始...")

                ve = self._verify_thread_cancel
                verify_result = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: verify_image_hash(
                        output_path,
                        result.source_hashes,
                        buffer_size=job.buffer_size,
                        progress_callback=lambda p, t: self._progress.update(
                            {"copied_bytes": p, "total_bytes": t}),
                        cancel_event=ve,
                        md5=job.hash_md5,
                        sha1=job.hash_sha1,
                        sha256=job.hash_sha256,
                        sha512=job.hash_sha512,
                    ),
                )

                result.verify_hashes = verify_result["computed"]
                if verify_result.get("cancelled"):
                    result.status = "cancelled"
                    result.error_code = "E3006"
                    result.error_message = "ユーザーによりキャンセルされました"
                    result.match_result = "pending"
                else:
                    result.match_result = (
                        "matched"
                        if verify_result["all_match"]
                        else "mismatched"
                    )

                    if verify_result["all_match"]:
                        logger.info("✅ イメージ検証: 全ハッシュ一致")
                    else:
                        logger.error("❌ イメージ検証: ハッシュ不一致")
                        result.error_code = "E5002"
                        result.error_message = (
                            "ソースとイメージのハッシュが一致しません"
                        )

                    if self._cancel_event.is_set():
                        result.status = "cancelled"
                        result.error_code = "E3006"
                        result.error_message = (
                            "ユーザーによりキャンセルされました"
                        )
                    else:
                        result.status = "completed"
            else:
                result.status = "completed"

        except asyncio.CancelledError:
            result.status = "cancelled"
            result.error_code = "E3006"
            result.error_message = "イメージングがキャンセルされました"
            logger.info("イメージング: CancelledError")
            raise
        except (OSError, IOError) as e:
            result.status = "failed"
            result.error_message = str(e)
            es = str(e)
            result.error_code = "E1005" if "[E1005]" in es else "E1003"
            logger.error("イメージング I/O エラー: %s", e, exc_info=True)
        except Exception as e:
            result.status = "failed"
            result.error_message = f"予期せぬエラー: {e}"
            logger.error("イメージング未知エラー: %s", e, exc_info=True)

        finally:
            if buffer_mgr is not None:
                buffer_mgr.shutdown()
            if sfh is not None:
                sfh.close()
            if dev is not None:
                dev.close()

            elapsed = time.time() - start_time
            result.elapsed_seconds = round(elapsed, 2)

            if elapsed > 0 and result.copied_bytes > 0:
                result.avg_speed_mibps = round(
                    result.copied_bytes / elapsed / (1024 * 1024), 2)

            self._progress["status"] = result.status
            self._progress["error_count"] = result.error_count
            self._progress["error_sectors"] = result.error_sectors
            logger.info(
                f"イメージング終了: status={result.status}, "
                f"time={elapsed:.1f}s, speed={result.avg_speed_mibps} MiB/s")

            if result.status in ("cancelled", "failed"):
                entries = detect_incomplete_files(
                    str(Path(job.output_dir)),
                    ["image*.dd", "image.dd"],
                )
                result.incomplete_file_records = entries
                result.incomplete_files = [e["path"] for e in entries]
                result.incomplete_total_bytes = sum(
                    e["size_bytes"] for e in entries
                )

            # エラーマップ保存
            if result.error_sectors:
                error_map_path = Path(job.output_dir) / "error_map.json"
                with open(error_map_path, "w") as f:
                    json.dump({
                        "error_count": result.error_count,
                        "error_sectors": result.error_sectors,
                    }, f, indent=2)
                logger.info(f"エラーマップ保存: {error_map_path}")

        return result

    async def run(self, job: ImagingJobParams) -> ImagingResult:
        """メインイメージングフロー（execute のエイリアス）"""
        return await self.execute(job)

    def set_progress_callback(self, callback: Callable) -> None:
        """進捗コールバック設定（UI更新用）"""
        self._progress_callback = callback

    def get_progress(self) -> dict:
        """現在の進捗を取得"""
        return self._progress.copy()

    async def cancel(self) -> None:
        """イメージングをキャンセル"""
        self._cancel_event.set()
        self._verify_thread_cancel.set()
        logger.info("イメージングキャンセル要求")

    async def pause(self) -> None:
        """一時停止"""
        self._pause_event.clear()
        self._progress["status"] = "paused"
        logger.info("イメージング一時停止")

    async def resume(self) -> None:
        """再開"""
        self._pause_event.set()
        self._progress["status"] = "imaging"
        logger.info("イメージング再開")
