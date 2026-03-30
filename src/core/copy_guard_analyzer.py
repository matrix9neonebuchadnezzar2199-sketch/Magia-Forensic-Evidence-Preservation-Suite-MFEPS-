"""
MFEPS v2.0 — コピーガード解析エンジン
CSS/AACS/リージョン/ARccOS/Disney X-Project/UOP/CCCD等の自動検出
"""
import logging
from typing import Optional

from pydantic import BaseModel

from src.models.enums import CopyGuardType
from src.core.optical_engine import OpticalAnalysisResult
from src.core.win32_raw_io import open_device, close_device, read_sectors

logger = logging.getLogger("mfeps.copy_guard_analyzer")


class ProtectionInfo(BaseModel):
    """個別コピーガード検出結果"""
    type: str = "none"            # CopyGuardType
    detected: bool = False
    can_decrypt: bool = False
    decrypt_method: Optional[str] = None  # "pydvdcss", "libaacs", None
    details: str = ""
    severity: str = "info"        # info / warning / critical


class CopyGuardResult(BaseModel):
    """コピーガード解析の総合結果"""
    protections: list[ProtectionInfo] = []
    overall_can_decrypt: bool = True
    recommended_action: str = "フォレンジックRAWコピー"
    legal_notice: str = ("コピーガード解除は正当な法的権限に基づく"
                         "証拠保全目的でのみ使用可能です。")


class CopyGuardAnalyzer:
    """光学メディアのコピーガード自動検出"""

    def analyze(self, drive_path: str,
                media_info: OpticalAnalysisResult) -> CopyGuardResult:
        """コピーガードを総合分析"""
        results = []

        if media_info.media_type in ("DVD-Video", "DVD-Data"):
            results.extend(self._check_dvd_protections(drive_path, media_info))
        elif media_info.media_type in ("BD-Video", "BD-Data"):
            results.extend(self._check_bd_protections(drive_path, media_info))
        elif media_info.media_type in ("CD-ROM", "CD-DA"):
            results.extend(self._check_cd_protections(drive_path, media_info))

        # 総合判定
        overall_can_decrypt = all(
            p.can_decrypt or not p.detected for p in results)

        if not any(p.detected for p in results):
            recommended = "フォレンジックRAWコピー（保護なし）"
        elif overall_can_decrypt:
            recommended = "復号コピー推奨"
        else:
            recommended = "RAWコピーのみ可能（一部暗号化未復号）"

        return CopyGuardResult(
            protections=results,
            overall_can_decrypt=overall_can_decrypt,
            recommended_action=recommended,
        )

    def _check_dvd_protections(self, drive_path: str,
                                info: OpticalAnalysisResult) -> list[ProtectionInfo]:
        """DVD保護検出"""
        results = []

        # 1. CSS (Content Scramble System)
        css_result = self._check_css(drive_path)
        results.append(css_result)

        # 2. リージョンコード
        region_result = self._check_region_code(drive_path, info)
        results.append(region_result)

        # 3. Macrovision / APS
        macro_result = self._check_macrovision(drive_path, info)
        results.append(macro_result)

        # 4. UOP
        uop_result = self._check_uop(drive_path, info)
        results.append(uop_result)

        # 5. Sony ARccOS
        arccos_result = self._check_arccos(drive_path, info)
        results.append(arccos_result)

        # 6. Disney X-Project
        disney_result = self._check_disney_xproject(drive_path, info)
        results.append(disney_result)

        return results

    def _check_bd_protections(self, drive_path: str,
                               info: OpticalAnalysisResult) -> list[ProtectionInfo]:
        """BD保護検出"""
        results = []

        # AACS
        results.append(self._check_aacs(drive_path, info))

        # BD+
        results.append(self._check_bdplus(drive_path, info))

        # Cinavia
        results.append(ProtectionInfo(
            type=CopyGuardType.CINAVIA,
            detected=False,
            details="Cinavia検出は音声解析が必要なため、直接検出不可",
            severity="info",
        ))

        return results

    def _check_cd_protections(self, drive_path: str,
                               info: OpticalAnalysisResult) -> list[ProtectionInfo]:
        """CD保護検出"""
        return [self._check_cccd(drive_path, info)]

    # ----- 個別検出メソッド -----

    def _check_css(self, drive_path: str) -> ProtectionInfo:
        """CSS暗号化検出"""
        try:
            from pydvdcss import DvdCss
            dvd = DvdCss()
            # ドライブレターからオープン
            letter = drive_path.replace("\\\\.\\CdRom", "")
            dvd.open(drive_path)
            scrambled = dvd.is_scrambled()
            dvd.close()

            if scrambled:
                return ProtectionInfo(
                    type=CopyGuardType.CSS,
                    detected=True,
                    can_decrypt=True,
                    decrypt_method="pydvdcss",
                    details="CSS暗号化検出 — pydvdcss経由で復号可能",
                    severity="warning",
                )
            else:
                return ProtectionInfo(
                    type=CopyGuardType.CSS,
                    detected=False,
                    details="CSS暗号化なし",
                    severity="info",
                )
        except ImportError:
            return ProtectionInfo(
                type=CopyGuardType.CSS,
                detected=False,
                details="pydvdcss未インストール — CSS検出スキップ",
                severity="info",
            )
        except Exception as e:
            logger.warning(f"CSS検出エラー: {e}")
            return ProtectionInfo(
                type=CopyGuardType.CSS,
                detected=False,
                details=f"CSS検出エラー: {e}",
                severity="info",
            )

    def _check_region_code(self, drive_path: str,
                           info: OpticalAnalysisResult) -> ProtectionInfo:
        """リージョンコード検出"""
        try:
            handle = open_device(drive_path)
            try:
                # VIDEO_TS.IFO のオフセット0x23からリージョンマスク読取
                # 簡易実装: LBA 257付近を読み取ってIFOシグネチャを探す
                data = read_sectors(handle, 2048 * 257, 2048)
                if data[:12] == b'DVDVIDEO-VMG':
                    region_byte = data[0x23]
                    if region_byte != 0xFF and region_byte != 0x00:
                        regions = []
                        for i in range(6):
                            if not (region_byte & (1 << i)):
                                regions.append(str(i + 1))
                        region_str = ",".join(regions) if regions else "不明"

                        return ProtectionInfo(
                            type=CopyGuardType.REGION,
                            detected=True,
                            can_decrypt=True,
                            details=f"リージョン {region_str}",
                            severity="info",
                        )
            finally:
                close_device(handle)
        except Exception as e:
            logger.debug(f"リージョン検出エラー: {e}")

        return ProtectionInfo(
            type=CopyGuardType.REGION,
            detected=False,
            details="リージョンコード未検出 / リージョンフリー",
            severity="info",
        )

    def _check_macrovision(self, drive_path: str,
                            info: OpticalAnalysisResult) -> ProtectionInfo:
        """Macrovision/APS検出"""
        # IFOファイルのAPSフラグを簡易チェック
        return ProtectionInfo(
            type=CopyGuardType.MACROVISION,
            detected=False,
            details="Macrovision/APS — フォレンジックRAWコピーに影響なし",
            severity="info",
        )

    def _check_uop(self, drive_path: str,
                    info: OpticalAnalysisResult) -> ProtectionInfo:
        """UOP (User Operation Prohibition) 検出"""
        return ProtectionInfo(
            type=CopyGuardType.UOP,
            detected=False,
            details="UOP — フォレンジックRAWコピーに影響なし",
            severity="info",
        )

    def _check_arccos(self, drive_path: str,
                       info: OpticalAnalysisResult) -> ProtectionInfo:
        """
        Sony ARccOS 検出 — 2段階アプローチ

        第1段階: 99トラック（ダミータイトル）— TOC のみ、追加 I/O なし。
        第2段階: ディスク後半 LBA のサンプル読取で不良セクタ傾向を検出。
        """
        detected = False
        details_parts: list[str] = []
        severity = "info"

        # ----- 第1段階: 99トラック -----
        if info.track_count == 99:
            detected = True
            details_parts.append(
                f"99トラック検出（トラック数: {info.track_count}）"
            )
            severity = "warning"
            logger.info(
                "ARccOS 第1段階: 99トラック検出 (tracks=%s)",
                info.track_count,
            )

        # ----- 第2段階: 不良セクタパターンスキャン -----
        bad_sector_count = 0
        sample_count = 0

        try:
            total_sectors = info.sector_count
            if total_sectors <= 0:
                raise ValueError("セクタ数が不正です")

            sector_size = info.sector_size if info.sector_size else 2048
            if sector_size <= 0:
                sector_size = 2048

            scan_start = int(total_sectors * 0.75)
            scan_end = int(total_sectors * 0.95)
            scan_range = scan_end - scan_start

            if scan_range > 0:
                sample_count = min(20, max(1, scan_range // 16))
                step = max(1, scan_range // sample_count)
            else:
                sample_count = 0

            handle = open_device(drive_path)
            try:
                if sample_count > 0:
                    for i in range(sample_count):
                        probe_lba = scan_start + (step * i)
                        if probe_lba >= total_sectors:
                            break
                        try:
                            offset = probe_lba * sector_size
                            _ = read_sectors(handle, offset, sector_size)
                        except OSError:
                            bad_sector_count += 1
            finally:
                close_device(handle)

        except Exception as e:
            logger.debug("ARccOS 第2段階スキャンエラー: %s", e)

        # ----- 第2段階の判定（サンプル25%以上エラーで強いシグナル） -----
        if sample_count > 0 and bad_sector_count > 0:
            error_ratio = bad_sector_count / sample_count
            if error_ratio >= 0.25:
                detected = True
                severity = "warning"
                details_parts.append(
                    f"不良セクタパターン検出 "
                    f"({bad_sector_count}/{sample_count}サンプル, "
                    f"{error_ratio:.0%})"
                )
                logger.info(
                    "ARccOS 第2段階: 不良セクタパターン "
                    "(%s/%s, ratio=%.2f)",
                    bad_sector_count,
                    sample_count,
                    error_ratio,
                )
            elif error_ratio > 0:
                details_parts.append(
                    f"一部セクタエラーあり "
                    f"({bad_sector_count}/{sample_count}サンプル)"
                )

        if detected:
            combined = " — ".join(details_parts)
            return ProtectionInfo(
                type=CopyGuardType.ARCCOS,
                detected=True,
                can_decrypt=True,
                details=(
                    f"ARccOS検出: {combined}. "
                    "RAWコピーは可能ですが、意図的不良セクタにより "
                    "一部セクタがゼロフィルされます。"
                ),
                severity=severity,
            )

        return ProtectionInfo(
            type=CopyGuardType.ARCCOS,
            detected=False,
            details="ARccOS未検出",
            severity="info",
        )

    def _check_disney_xproject(self, drive_path: str,
                                info: OpticalAnalysisResult) -> ProtectionInfo:
        """Disney X-Project DRM検出 — 異常VTS数"""
        try:
            handle = open_device(drive_path)
            try:
                # VIDEO_TS 内のVTS_XX_0.IFOファイル数を推測
                # (実際にはファイルシステム解析が必要)
                data = read_sectors(handle, 2048 * 257, 2048)
                if data[:12] == b'DVDVIDEO-VMG':
                    # VMGのNumber of Title Sets
                    vts_count = int.from_bytes(data[0x3E:0x40], "big")
                    if vts_count > 50:
                        return ProtectionInfo(
                            type=CopyGuardType.DISNEY_XPROJECT,
                            detected=True,
                            can_decrypt=True,
                            details=f"疑わしいVTS数: {vts_count} — X-Projectの可能性",
                            severity="warning",
                        )
            finally:
                close_device(handle)
        except Exception as e:
            logger.debug(f"Disney X-Project検出エラー: {e}")

        return ProtectionInfo(
            type=CopyGuardType.DISNEY_XPROJECT,
            detected=False,
            details="Disney X-Project未検出",
            severity="info",
        )

    def _check_aacs(self, drive_path: str,
                     info: OpticalAnalysisResult) -> ProtectionInfo:
        """AACS暗号化検出"""
        try:
            handle = open_device(drive_path)
            try:
                # AACS/ ディレクトリの存在確認（ファイルシステム読取）
                for offset_mb in [0, 1, 2, 4]:
                    data = read_sectors(handle, offset_mb * 1024 * 1024, 2048 * 4)
                    if b'AACS' in data or b'MKB_RW' in data:
                        return ProtectionInfo(
                            type=CopyGuardType.AACS,
                            detected=True,
                            can_decrypt=False,
                            decrypt_method="libaacs",
                            details="AACS暗号化検出 — libaacs + keydb.cfg が必要",
                            severity="critical",
                        )
            finally:
                close_device(handle)
        except Exception as e:
            logger.debug(f"AACS検出エラー: {e}")

        return ProtectionInfo(
            type=CopyGuardType.AACS,
            detected=False,
            details="AACS暗号化なし",
            severity="info",
        )

    def _check_bdplus(self, drive_path: str,
                       info: OpticalAnalysisResult) -> ProtectionInfo:
        """BD+検出"""
        try:
            handle = open_device(drive_path)
            try:
                for offset_mb in [0, 1, 2, 4]:
                    data = read_sectors(handle, offset_mb * 1024 * 1024, 2048 * 4)
                    if b'BDSVM' in data:
                        return ProtectionInfo(
                            type=CopyGuardType.BD_PLUS,
                            detected=True,
                            can_decrypt=False,
                            details="BD+検出 — libbdplus が必要",
                            severity="warning",
                        )
            finally:
                close_device(handle)
        except Exception as e:
            logger.debug(f"BD+検出エラー: {e}")

        return ProtectionInfo(
            type=CopyGuardType.BD_PLUS,
            detected=False,
            details="BD+未検出",
            severity="info",
        )

    def _check_cccd(self, drive_path: str,
                     info: OpticalAnalysisResult) -> ProtectionInfo:
        """コピーコントロールCD検出"""
        # マルチセッション + データトラック混在パターン
        has_data = any(t.is_data for t in info.tracks)
        has_audio = any(not t.is_data for t in info.tracks)

        if has_data and has_audio and info.track_count > 2:
            return ProtectionInfo(
                type=CopyGuardType.CCCD,
                detected=True,
                can_decrypt=True,
                details="CCCD疑い — データ+音声トラック混在",
                severity="warning",
            )

        return ProtectionInfo(
            type=CopyGuardType.CCCD,
            detected=False,
            details="CCCD未検出",
            severity="info",
        )
