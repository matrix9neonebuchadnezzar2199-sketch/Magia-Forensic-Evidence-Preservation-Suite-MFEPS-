"""
MFEPS v2.0 — 光学メディア (CD/DVD/BD) イメージングエンジン
TOC解析、メディア種別判定、CSS/AACS復号統合
"""
import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel

from src.core.hash_engine import TripleHashEngine
from src.core.win32_raw_io import (
    open_device, close_device, read_cdrom_toc, read_sectors, scsi_read_cd,
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

            # 容量計算
            if result.tracks:
                last_track = result.tracks[-1]
                # おおよその容量
                result.sector_count = last_track.address_lba
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
        self._cancel_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._progress = {}

    async def image_optical(
        self,
        drive_path: str,
        output_path: str,
        analysis: OpticalAnalysisResult,
        use_pydvdcss: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> dict:
        """
        光学メディアをイメージングする。

        use_pydvdcss=True の場合: DvdCssReader で CSS 復号しつつ読取。
        初期化失敗・ImportError 時は RAW にフォールバック。
        ハッシュは書き込んだバイト列（復号後）に対して計算する。
        """
        start_time = time.time()
        hash_engine = TripleHashEngine()
        error_count = 0
        error_sectors = []

        sector_size = analysis.sector_size
        total_sectors = analysis.sector_count
        total_bytes = total_sectors * sector_size

        css_reader: Any = None  # DvdCssReader | None
        decrypt_pydvdcss = False
        decrypt_method: str | None = None
        css_scrambled_snapshot: bool | None = None

        logger.info(
            f"光学イメージング開始: {drive_path}, "
            f"sectors={total_sectors}, sector_size={sector_size}, "
            f"use_pydvdcss={use_pydvdcss}")

        handle = None
        output_file = None

        try:
            # ----- pydvdcss（CSS 復号）初期化 -----
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

            if not decrypt_pydvdcss:
                handle = open_device(drive_path)

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            output_file = open(output_path, "wb")

            current_lba = 0
            copied_bytes = 0

            while current_lba < total_sectors:
                if self._cancel_event.is_set():
                    break
                await self._pause_event.wait()

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
                            await asyncio.sleep(wait)
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
                    progress_callback({
                        "copied_bytes": copied_bytes,
                        "total_bytes": total_bytes,
                        "current_lba": current_lba,
                        "total_sectors": total_sectors,
                        "error_count": error_count,
                        "decrypt_mode": (
                            "pydvdcss" if decrypt_pydvdcss else "raw"
                        ),
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
        }

    async def cancel(self):
        self._cancel_event.set()

    async def pause(self):
        self._pause_event.clear()

    async def resume(self):
        self._pause_event.set()
