"""
MFEPS v2.1.0 — 光学メディア (CD/DVD/BD) イメージングエンジン
TOC解析、メディア種別判定、CSS/AACS復号統合
"""
import asyncio
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel

from src.core.hash_engine import TripleHashEngine
from src.core.win32_raw_io import (
    open_device,
    close_device,
    read_cdrom_toc,
    read_sectors,
    scsi_read_cd,
    get_disk_length,
)

logger = logging.getLogger("mfeps.optical_engine")


class TrackInfo(BaseModel):
    track_number: int = 0
    is_data: bool = True
    address_lba: int = 0
    control: int = 0
    sector_size: int = 2048


class OpticalAnalysisResult(BaseModel):
    drive_path: str = ""
    media_type: str = "Unknown"    # CD-ROM, CD-DA, DVD-Data, DVD-Video, BD-Data, BD-Video
    file_system: str = ""          # ISO9660, UDF, UDF+ISO9660
    capacity_bytes: int = 0
    sector_size: int = 2048
    sector_count: int = 0
    track_count: int = 0
    session_count: int = 1
    tracks: list[TrackInfo] = []
    is_multisession: bool = False
    udf_version: Optional[str] = None
    volume_label: Optional[str] = None


class OpticalMediaAnalyzer:
    """光学メディア種別判定 + 構造解析"""

    def analyze(self, drive_path: str) -> OpticalAnalysisResult:
        """メディア全体の分析"""
        result = OpticalAnalysisResult(drive_path=drive_path)
        handle = None

        try:
            handle = open_device(drive_path)

            # TOC読取
            try:
                toc = read_cdrom_toc(handle)
                result.track_count = toc["track_count"]
                result.tracks = [
                    TrackInfo(
                        track_number=t["track_number"],
                        is_data=t["is_data"],
                        address_lba=t["address_lba"],
                        control=t["control"],
                    )
                    for t in toc["tracks"]
                ]
            except Exception as e:
                logger.warning(f"TOC 読取失敗: {e}")

            # メディア種別判定
            result.media_type = self._detect_media_type(handle, drive_path, result)

            # セクタサイズ設定
            if result.media_type == "CD-DA":
                result.sector_size = 2352
            else:
                result.sector_size = 2048

            # 容量計算: IOCTL のディスク長を優先（DVD/BD/データ CD で有効なことが多い）
            try:
                length_bytes = get_disk_length(handle)
                if length_bytes > 0:
                    result.capacity_bytes = length_bytes
                    result.sector_count = (
                        (length_bytes + result.sector_size - 1)
                        // result.sector_size
                    )
            except OSError:
                length_bytes = 0

            if result.capacity_bytes <= 0 and result.tracks:
                leadout = [t for t in result.tracks if t.track_number == 0xAA]
                if leadout:
                    result.sector_count = leadout[0].address_lba
                else:
                    max_lba = max(t.address_lba for t in result.tracks)
                    result.sector_count = max_lba + 32768
                result.capacity_bytes = result.sector_count * result.sector_size

            # ファイルシステム判定
            try:
                result.file_system = self._detect_filesystem(handle)
            except Exception:
                pass

            logger.info(
                f"光学メディア分析: type={result.media_type}, "
                f"fs={result.file_system}, "
                f"capacity={result.capacity_bytes / (1024**2):.0f} MiB")

        except Exception as e:
            logger.error(f"光学メディア分析エラー: {e}")
        finally:
            if handle:
                close_device(handle)

        return result

    def _detect_media_type(self, handle, drive_path: str,
                           result: OpticalAnalysisResult) -> str:
        """メディア種別を判定"""
        # CD-DA: 全トラックがオーディオ
        if result.tracks:
            all_audio = all(not t.is_data for t in result.tracks)
            if all_audio:
                return "CD-DA"

        # DVD/BD 判定: 先頭セクタからファイルシステム情報を読み取る
        try:
            data = read_sectors(handle, 32768, 2048)  # PVD at LBA 16

            # UDF / ISO9660 判定
            if data[1:6] == b'CD001':
                # ISO9660 PVD
                volume_label = data[40:72].decode("ascii", errors="replace").strip()

                # DVD-Video: VIDEO_TS フォルダの存在
                try:
                    # パス テーブルからVIDEO_TSを検索
                    root_data = read_sectors(handle, 32768 + 2048 * 2, 2048 * 4)
                    if b'VIDEO_TS' in root_data:
                        return "DVD-Video"
                    elif b'BDMV' in root_data:
                        return "BD-Video"
                except Exception:
                    pass

                # セクタ数からCD/DVD/BD簡易判定
                if result.sector_count > 2_300_000:  # ~4.7GB
                    return "BD-Data" if result.sector_count > 12_000_000 else "DVD-Data"
                else:
                    return "CD-ROM"

        except Exception as e:
            logger.debug(f"メディア種別判定のセクタ読取失敗: {e}")

        # フォールバック: トラック構成から推定
        if result.sector_count > 2_300_000:
            return "DVD-Data"
        return "CD-ROM"

    def _detect_filesystem(self, handle) -> str:
        """ファイルシステム判定"""
        try:
            data = read_sectors(handle, 32768, 2048)
            if data[1:6] == b'CD001':
                # BEA01 / NSR02/NSR03 チェック（UDF）
                try:
                    udf_data = read_sectors(handle, 32768 + 2048, 2048)
                    if b'BEA01' in udf_data or b'NSR0' in udf_data:
                        return "UDF+ISO9660"
                except Exception:
                    pass
                return "ISO9660"

            # UDFのみ
            try:
                udf_data = read_sectors(handle, 32768 + 2048, 2048)
                if b'BEA01' in udf_data or b'NSR0' in udf_data:
                    return "UDF"
            except Exception:
                pass

        except Exception:
            pass
        return "Unknown"


class OpticalImagingEngine:
    """光学メディアイメージングエンジン"""

    def __init__(self, buffer_sectors: int = 32, retry_count: int = 5):
        self.buffer_sectors = buffer_sectors  # 一度に読むセクタ数
        self.retry_count = retry_count
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._progress = {}

    async def image_optical(
        self,
        drive_path: str,
        output_path: str,
        analysis: OpticalAnalysisResult,
        use_pydvdcss: bool = False,
        use_aacs: bool = False,
        progress_callback: Optional[Callable] = None,
        *,
        hash_md5: bool = True,
        hash_sha1: bool = True,
        hash_sha256: bool = True,
        hash_sha512: bool = False,
    ) -> dict:
        self._cancel_event.clear()
        self._pause_event.set()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._image_optical_sync,
            drive_path,
            output_path,
            analysis,
            use_pydvdcss,
            use_aacs,
            progress_callback,
            hash_md5,
            hash_sha1,
            hash_sha256,
            hash_sha512,
        )

    def _image_optical_sync(
        self,
        drive_path: str,
        output_path: str,
        analysis: OpticalAnalysisResult,
        use_pydvdcss: bool = False,
        use_aacs: bool = False,
        progress_callback: Optional[Callable] = None,
        hash_md5: bool = True,
        hash_sha1: bool = True,
        hash_sha256: bool = True,
        hash_sha512: bool = False,
    ) -> dict:
        """
        光学メディアをイメージングする。

        use_pydvdcss: DvdCssReader（CSS）。use_aacs: AacsReader（AACS）。
        いずれも初期化失敗時は RAW にフォールバック。
        """
        start_time = time.time()
        hash_engine = TripleHashEngine(
            md5=hash_md5,
            sha1=hash_sha1,
            sha256=hash_sha256,
            sha512=hash_sha512,
        )
        error_count = 0
        error_sectors = []

        sector_size = analysis.sector_size
        total_sectors = analysis.sector_count
        total_bytes = total_sectors * sector_size

        css_reader: Any = None
        aacs_reader: Any = None
        decrypt_pydvdcss = False
        decrypt_aacs = False
        decrypt_method: str | None = None
        css_scrambled_snapshot: bool | None = None
        aacs_mkb_snapshot: int | None = None

        logger.info(
            f"光学イメージング開始: {drive_path}, "
            f"sectors={total_sectors}, sector_size={sector_size}, "
            f"use_pydvdcss={use_pydvdcss}, use_aacs={use_aacs}"
        )

        handle = None
        output_file = None

        try:
            # ----- pydvdcss（CSS） -----
            if use_pydvdcss:
                if sector_size != 2048:
                    logger.warning(
                        "pydvdcss は 2048 バイト/セクタのみ対応のため RAW にフォールバック "
                        f"(sector_size={sector_size})"
                    )
                    use_pydvdcss = False
                else:
                    try:
                        from src.core.dvdcss_reader import DvdCssReader as _Dvd

                        css_reader = _Dvd()
                        css_reader.open(drive_path)
                        decrypt_pydvdcss = True
                        decrypt_method = "pydvdcss"
                        css_scrambled_snapshot = css_reader.is_scrambled
                        logger.info(
                            "CSS復号モード有効: scrambled=%s",
                            css_scrambled_snapshot,
                        )
                    except ImportError:
                        logger.warning(
                            "pydvdcss 未インストール — RAW フォールバック"
                        )
                        css_reader = None
                        use_pydvdcss = False
                    except Exception as e:
                        logger.warning(
                            "pydvdcss 初期化失敗 — RAW フォールバック: %s", e
                        )
                        css_reader = None
                        use_pydvdcss = False
                        decrypt_method = None

            # ----- libaacs（AACS）— CSS と同時には使わない -----
            if use_aacs and not decrypt_pydvdcss:
                if sector_size != 2048:
                    logger.warning(
                        "libaacs は 2048 バイト/セクタのみ想定のため RAW にフォールバック "
                        f"(sector_size={sector_size})"
                    )
                    use_aacs = False
                else:
                    try:
                        from src.core.aacs_reader import AacsReader as _Aacs

                        aacs_reader = _Aacs()
                        if aacs_reader.open(drive_path):
                            decrypt_aacs = True
                            decrypt_method = "libaacs"
                            aacs_mkb_snapshot = aacs_reader.mkb_version
                            logger.info(
                                "AACS復号モード有効: MKB v%s",
                                aacs_mkb_snapshot,
                            )
                        else:
                            logger.warning("libaacs 復号不可 — RAW フォールバック")
                            aacs_reader = None
                            use_aacs = False
                    except Exception as e:
                        logger.warning(
                            "libaacs 初期化失敗 — RAW フォールバック: %s", e
                        )
                        aacs_reader = None
                        use_aacs = False
                        decrypt_method = None

            if not decrypt_pydvdcss and not decrypt_aacs:
                handle = open_device(drive_path)

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            output_file = open(output_path, "wb")

            current_lba = 0
            copied_bytes = 0

            while current_lba < total_sectors:
                if self._cancel_event.is_set():
                    break
                self._pause_event.wait()

                chunk_start_lba = current_lba
                remaining = total_sectors - current_lba
                chunk_sectors = min(self.buffer_sectors, remaining)
                chunk_size = chunk_sectors * sector_size
                offset = current_lba * sector_size

                data = None
                for attempt in range(self.retry_count):
                    try:
                        if decrypt_pydvdcss and css_reader:
                            data = css_reader.read_sectors(
                                chunk_start_lba,
                                chunk_sectors,
                                is_title_start=(chunk_start_lba == 0),
                            )
                        elif decrypt_aacs and aacs_reader:
                            data = aacs_reader.read_sectors(
                                chunk_start_lba,
                                chunk_sectors,
                            )
                        elif analysis.media_type == "CD-DA":
                            data = scsi_read_cd(
                                handle, current_lba, chunk_sectors,
                                sector_size=2352)
                        else:
                            data = read_sectors(handle, offset, chunk_size)
                        break
                    except (OSError, IOError) as e:
                        if attempt < self.retry_count - 1:
                            wait = 0.1 * (2 ** attempt)
                            logger.warning(
                                f"リトライ {attempt+1}/{self.retry_count}: "
                                f"LBA={current_lba}, wait={wait}s, error={e}"
                            )
                            time.sleep(wait)
                        else:
                            logger.error(f"読取失敗（ゼロフィル）: LBA={current_lba}")
                            data = b"\x00" * chunk_size
                            error_count += 1
                            error_sectors.append(current_lba)

                if data:
                    hash_engine.update(data)
                    output_file.write(data)
                    copied_bytes += len(data)

                current_lba += chunk_sectors

                if progress_callback:
                    _dm = (
                        "pydvdcss"
                        if decrypt_pydvdcss
                        else ("libaacs" if decrypt_aacs else "raw")
                    )
                    progress_callback({
                        "copied_bytes": copied_bytes,
                        "total_bytes": total_bytes,
                        "current_lba": current_lba,
                        "total_sectors": total_sectors,
                        "error_count": error_count,
                        "decrypt_mode": _dm,
                    })

            output_file.flush()
            os.fsync(output_file.fileno())

        except Exception as e:
            logger.error(f"光学イメージングエラー: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "decrypt_method": decrypt_method,
            }
        finally:
            if output_file:
                output_file.close()
            if handle:
                close_device(handle)
            if css_reader:
                css_reader.close()
            if aacs_reader:
                aacs_reader.close()

        elapsed = time.time() - start_time
        source_hashes = hash_engine.hexdigests()

        logger.info(
            f"光学イメージング完了: {copied_bytes} bytes, "
            f"{elapsed:.1f}s, errors={error_count}, "
            f"decrypt={decrypt_method or 'none'}"
        )

        return {
            "status": "cancelled" if self._cancel_event.is_set() else "completed",
            "source_hashes": source_hashes,
            "copied_bytes": copied_bytes,
            "total_bytes": total_bytes,
            "error_count": error_count,
            "error_sectors": error_sectors,
            "elapsed_seconds": elapsed,
            "output_path": output_path,
            "decrypt_method": decrypt_method,
            "css_scrambled": css_scrambled_snapshot,
            "aacs_mkb_version": aacs_mkb_snapshot,
        }

    async def cancel(self):
        self._cancel_event.set()

    async def pause(self):
        self._pause_event.clear()

    async def resume(self):
        self._pause_event.set()
