"""
MFEPS v2.1.0 — 光学メディア (CD/DVD/BD) イメージングエンジン
TOC解析、メディア種別判定、CSS/AACS復号統合
"""
import asyncio
import logging
import os
import threading
import time
from functools import partial
from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

from src.core.hash_engine import TripleHashEngine
from src.core.win32_raw_io import (
    open_device,
    close_device,
    device_handle,
    read_cdrom_toc,
    read_sectors,
    scsi_read_cd,
    get_disk_length,
)

logger = logging.getLogger("mfeps.optical_engine")

if TYPE_CHECKING:
    from src.core.copy_guard_analyzer import CopyGuardResult

# 容量選択・メディア種別のしきい値（バイト）
# DVD 以上のディスクでは IOCTL が TOC リードアウトより信頼しやすい（CD の 150 セクタ問題は CD 特有）
_OPTICAL_DVD_HINT_BYTES = 700_000_000
# ISO9660 PVD のみから BD / DVD / CD を切り分けるときの容量下限
_OPTICAL_BD_DATA_BYTES = 25_000_000_000


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
    # B-1: 容量ソース診断
    ioctl_length_bytes: int = 0
    toc_leadout_bytes: int = 0
    capacity_source: str = ""


class OpticalImagingResult(BaseModel):
    """光学イメージング結果"""

    status: str = "completed"
    error: str = ""
    source_hashes: dict[str, str] = Field(default_factory=dict)
    copied_bytes: int = 0
    total_bytes: int = 0
    error_count: int = 0
    error_sectors: list[int] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
    output_path: str = ""
    decrypt_method: Optional[str] = None
    css_scrambled: Optional[bool] = None
    aacs_mkb_version: Optional[int] = None
    error_code: Optional[str] = None


class OpticalMediaAnalyzer:
    """光学メディア種別判定 + 構造解析"""

    @staticmethod
    def _toc_leadout_and_max_bytes(
        result: OpticalAnalysisResult, sector_size: int
    ) -> tuple[int, int]:
        """TOC からリードアウト換算バイトと max_lba 推定バイトを求める。"""
        toc_leadout_bytes = 0
        toc_max_bytes = 0
        if not result.tracks:
            return toc_leadout_bytes, toc_max_bytes
        leadout = [t for t in result.tracks if t.track_number == 0xAA]
        if leadout:
            toc_leadout_bytes = leadout[0].address_lba * sector_size
            result.toc_leadout_bytes = toc_leadout_bytes
        else:
            max_lba = max(t.address_lba for t in result.tracks)
            toc_max_bytes = (max_lba + 32768) * sector_size
        return toc_leadout_bytes, toc_max_bytes

    def _fill_optical_capacity(
        self,
        result: OpticalAnalysisResult,
        ioctl_bytes: int,
        toc_leadout_bytes: int,
        toc_max_bytes: int,
        *,
        prefer_ioctl_first: bool,
    ) -> None:
        """IOCTL / TOC から capacity_bytes・sector_count・capacity_source を設定。"""
        ss = result.sector_size
        if prefer_ioctl_first:
            if ioctl_bytes > 0:
                result.capacity_bytes = ioctl_bytes
                result.sector_count = (ioctl_bytes + ss - 1) // ss
                result.capacity_source = "ioctl"
            elif toc_leadout_bytes > 0:
                result.capacity_bytes = toc_leadout_bytes
                result.sector_count = toc_leadout_bytes // ss
                result.capacity_source = "toc_leadout"
            elif toc_max_bytes > 0:
                result.capacity_bytes = toc_max_bytes
                result.sector_count = toc_max_bytes // ss
                result.capacity_source = "toc_max"
        else:
            # CD 系: B-1 — TOC リードアウト > IOCTL > TOC max
            if toc_leadout_bytes > 0:
                result.capacity_bytes = toc_leadout_bytes
                result.sector_count = toc_leadout_bytes // ss
                result.capacity_source = "toc_leadout"
            elif ioctl_bytes > 0:
                result.capacity_bytes = ioctl_bytes
                result.sector_count = (ioctl_bytes + ss - 1) // ss
                result.capacity_source = "ioctl"
            elif toc_max_bytes > 0:
                result.capacity_bytes = toc_max_bytes
                result.sector_count = toc_max_bytes // ss
                result.capacity_source = "toc_max"

        if result.capacity_bytes <= 0:
            logger.warning(
                "光学メディア容量を特定できませんでした: ioctl=%d, toc_leadout=%d",
                ioctl_bytes,
                toc_leadout_bytes,
            )
            if result.tracks:
                leadout_fb = [t for t in result.tracks if t.track_number == 0xAA]
                if leadout_fb:
                    result.sector_count = leadout_fb[0].address_lba
                else:
                    max_lba = max(t.address_lba for t in result.tracks)
                    result.sector_count = max_lba + 32768
                result.capacity_bytes = result.sector_count * result.sector_size
                result.capacity_source = "toc_fallback"

    def analyze(self, drive_path: str) -> OpticalAnalysisResult:
        """メディア全体の分析"""
        result = OpticalAnalysisResult(drive_path=drive_path)

        try:
            with device_handle(drive_path) as handle:
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

                ioctl_bytes = 0
                try:
                    ioctl_bytes = get_disk_length(handle)
                    result.ioctl_length_bytes = ioctl_bytes
                except OSError:
                    pass

                all_audio = bool(result.tracks) and all(
                    not t.is_data for t in result.tracks
                )

                if all_audio:
                    result.sector_size = 2352
                    toc_leadout_bytes, toc_max_bytes = (
                        self._toc_leadout_and_max_bytes(
                            result, result.sector_size
                        )
                    )
                    self._fill_optical_capacity(
                        result,
                        ioctl_bytes,
                        toc_leadout_bytes,
                        toc_max_bytes,
                        prefer_ioctl_first=False,
                    )
                    result.media_type = "CD-DA"
                else:
                    result.sector_size = 2048
                    toc_leadout_bytes, toc_max_bytes = (
                        self._toc_leadout_and_max_bytes(
                            result, result.sector_size
                        )
                    )
                    prefer_ioctl_first = (
                        ioctl_bytes > _OPTICAL_DVD_HINT_BYTES
                    )
                    self._fill_optical_capacity(
                        result,
                        ioctl_bytes,
                        toc_leadout_bytes,
                        toc_max_bytes,
                        prefer_ioctl_first=prefer_ioctl_first,
                    )
                    result.media_type = self._detect_media_type(
                        handle, drive_path, result
                    )

                try:
                    result.file_system = self._detect_filesystem(handle)
                except Exception:
                    pass

                logger.info(
                    f"光学メディア分析: type={result.media_type}, "
                    f"fs={result.file_system}, "
                    f"capacity={result.capacity_bytes / (1024**2):.0f} MiB"
                )

        except Exception as e:
            logger.error(f"光学メディア分析エラー: {e}")

        return result

    def _detect_media_type(self, handle, drive_path: str,
                           result: OpticalAnalysisResult) -> str:
        """メディア種別を判定（analyze 内で容量計算後に呼ぶこと）。"""
        cap = result.capacity_bytes or result.ioctl_length_bytes or 0

        # DVD/BD 判定: 先頭セクタからファイルシステム情報を読み取る
        try:
            data = read_sectors(handle, 32768, 2048)  # PVD at LBA 16

            # UDF / ISO9660 判定
            if data[1:6] == b'CD001':
                # ISO9660 PVD
                data[40:72].decode("ascii", errors="replace").strip()

                # DVD-Video: VIDEO_TS フォルダの存在
                try:
                    # パス テーブルからVIDEO_TSを検索
                    root_data = read_sectors(handle, 32768 + 2048 * 2, 2048 * 4)
                    if b'VIDEO_TS' in root_data:
                        return "DVD-Video"
                    if b'BDMV' in root_data:
                        return "BD-Video"
                except Exception:
                    pass

                # 容量ベース（sector_count は容量計算前だと常に 0 だったため cap を使用）
                if cap > _OPTICAL_BD_DATA_BYTES:
                    return "BD-Data"
                if cap > _OPTICAL_DVD_HINT_BYTES:
                    return "DVD-Data"
                return "CD-ROM"

        except Exception as e:
            logger.debug(f"メディア種別判定のセクタ読取失敗: {e}")

        # フォールバック: 容量から推定
        if cap > _OPTICAL_BD_DATA_BYTES:
            return "BD-Data"
        if cap > _OPTICAL_DVD_HINT_BYTES:
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

    def __init__(self, buffer_sectors: int = 512, retry_count: int = 5):
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
        pydvdcss_open_path: Optional[str] = None,
        copy_guard_result: Optional["CopyGuardResult"] = None,
    ) -> OpticalImagingResult:
        self._cancel_event.clear()
        self._pause_event.set()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(
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
                pydvdcss_open_path,
                copy_guard_result,
            ),
        )

    async def run(
        self,
        drive_path: str,
        output_path: str,
        analysis: OpticalAnalysisResult,
        **kwargs,
    ) -> OpticalImagingResult:
        """メインイメージングフロー（image_optical のエイリアス）"""
        return await self.image_optical(
            drive_path=drive_path,
            output_path=output_path,
            analysis=analysis,
            **kwargs,
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
        pydvdcss_open_path: Optional[str] = None,
        copy_guard_result: Optional["CopyGuardResult"] = None,
    ) -> OpticalImagingResult:
        """
        光学メディアをイメージングする。

        use_pydvdcss: DvdCssReader（CSS）。use_aacs: AacsReader（AACS）。
        いずれも初期化失敗時は RAW にフォールバック。
        copy_guard_result: CopyGuardAnalyzer の結果に基づき復号フラグを補正可能。
        """
        try:
            output_path = os.fspath(output_path)
        except TypeError:
            output_path = str(output_path)

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

        if copy_guard_result is not None:
            from src.models.enums import CopyGuardType

            for prot in copy_guard_result.protections:
                t = prot.type
                if (
                    t == CopyGuardType.CSS.value
                    and prot.detected
                    and prot.can_decrypt
                ):
                    if not use_pydvdcss:
                        logger.info(
                            "CopyGuard: CSS 検出かつ復号可能 — pydvdcss を有効化します"
                        )
                    use_pydvdcss = True
                if (
                    t == CopyGuardType.AACS.value
                    and prot.detected
                    and not prot.can_decrypt
                ):
                    if use_aacs:
                        logger.warning(
                            "CopyGuard: AACS 検出だが復号不可 — RAW にフォールバックします"
                        )
                    use_aacs = False

        if total_sectors <= 0:
            logger.error(
                "光学メディア容量が 0 です: total_sectors=%d, "
                "capacity_bytes=%s, capacity_source=%s",
                total_sectors,
                analysis.capacity_bytes,
                analysis.capacity_source,
            )
            return OpticalImagingResult(
                status="failed",
                error="メディア容量を取得できませんでした (total_sectors=0)",
                output_path=output_path,
                error_code="E8001",
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
                        css_reader.open(
                            drive_path,
                            pydvdcss_open_path=pydvdcss_open_path,
                        )
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
                    expected_chunk_len = chunk_size
                    if len(data) < expected_chunk_len:
                        missing_sectors = (
                            expected_chunk_len - len(data) + sector_size - 1
                        ) // sector_size
                        if missing_sectors > 0:
                            error_count += missing_sectors
                            error_sectors.extend(
                                range(
                                    chunk_start_lba + chunk_sectors - missing_sectors,
                                    chunk_start_lba + chunk_sectors,
                                )
                            )
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

        except (OSError, IOError) as e:
            logger.error("光学イメージング I/O エラー: %s", e, exc_info=True)
            return OpticalImagingResult(
                status="failed",
                error=str(e),
                decrypt_method=decrypt_method,
                error_code="E8002",
            )
        except Exception as e:
            logger.error("光学イメージング未知エラー: %s", e, exc_info=True)
            return OpticalImagingResult(
                status="failed",
                error=str(e),
                decrypt_method=decrypt_method,
                error_code="E8002",
            )
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

        return OpticalImagingResult(
            status=(
                "cancelled" if self._cancel_event.is_set() else "completed"
            ),
            source_hashes=source_hashes,
            copied_bytes=copied_bytes,
            total_bytes=total_bytes,
            error_count=error_count,
            error_sectors=error_sectors,
            elapsed_seconds=elapsed,
            output_path=output_path,
            decrypt_method=decrypt_method,
            css_scrambled=css_scrambled_snapshot,
            aacs_mkb_version=aacs_mkb_snapshot,
        )

    async def cancel(self):
        self._cancel_event.set()

    async def pause(self):
        self._pause_event.clear()

    async def resume(self):
        self._pause_event.set()
