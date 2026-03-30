"""
MFEPS v2.0 — デバイス検出モジュール
WMI 経由でブロックデバイス・光学ドライブを列挙
"""
import logging
import subprocess
import json
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger("mfeps.device_detector")


class PartitionInfo(BaseModel):
    """パーティション情報"""
    letter: str = ""
    file_system: str = ""
    size_bytes: int = 0
    free_bytes: int = 0


class DeviceInfo(BaseModel):
    """ブロックデバイス情報"""
    device_path: str = ""          # \\.\PhysicalDrive0
    drive_letters: list[str] = []  # ['E:', 'F:']
    model: str = ""                # "SanDisk Ultra"
    serial: str = ""               # "4C530001..."
    media_type: str = ""           # "USB", "Fixed", "Removable"
    interface_type: str = ""       # "USB", "SCSI", "IDE"
    capacity_bytes: int = 0
    sector_size: int = 512
    is_system_drive: bool = False
    is_readonly: bool = False
    partitions: list[PartitionInfo] = []
    index: int = 0


class OpticalDriveInfo(BaseModel):
    """光学ドライブ情報"""
    device_path: str = ""          # \\.\CdRom0
    drive_letter: str = ""         # 'D:'
    drive_model: str = ""          # "HL-DT-ST BD-RE"
    media_loaded: bool = False
    media_type: str = "NoMedia"    # "CD-ROM", "DVD-ROM", "DVD-Video", "BD-ROM", etc.
    capacity_bytes: int = 0
    sector_size: int = 2048
    track_count: int = 0
    toc_data: dict = {}


def detect_block_devices() -> list[DeviceInfo]:
    """PowerShell経由でブロックデバイスを列挙"""
    devices = []

    try:
        # PowerShell で物理ディスク情報を取得しJSON形式で出力
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_DiskDrive -ErrorAction SilentlyContinue | Select-Object Index,Model,SerialNumber,Size,MediaType,InterfaceType,BytesPerSector,Partitions | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15, encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:
            logger.error(f"デバイス情報取得失敗: {result.stderr}")
            return devices

        stdout = result.stdout.strip()
        if not stdout:
            return devices
            
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.error(f"JSONパースエラー: {e}")
            return devices

        if isinstance(data, dict):
            # 単一デバイスの場合はリスト化
            data = [data]

        for item in data:
            dev = _parse_device_json(item)
            if dev:
                devices.append(dev)

        # ドライブレターのマッピング
        _map_drive_letters(devices)

        # システムドライブ判定
        _detect_system_drive(devices)

        logger.info(f"ブロックデバイス検出: {len(devices)} 台")

    except subprocess.TimeoutExpired:
        logger.error("デバイス検出コマンドがタイムアウトしました")
    except Exception as e:
        logger.error(f"デバイス検出エラー: {e}")

    return devices


def _parse_device_json(data: dict) -> Optional[DeviceInfo]:
    """JSON出力を DeviceInfo に変換"""
    try:
        index = data.get("Index")
        if index is None or index < 0:
            return None

        size = data.get("Size") or 0
        sector_size = data.get("BytesPerSector") or 512

        return DeviceInfo(
            device_path=f"\\\\.\\PhysicalDrive{index}",
            index=index,
            model=str(data.get("Model") or "Unknown").strip(),
            serial=str(data.get("SerialNumber") or "").strip(),
            media_type=str(data.get("MediaType") or "").strip(),
            interface_type=str(data.get("InterfaceType") or "").strip(),
            capacity_bytes=int(size),
            sector_size=int(sector_size),
        )
    except (ValueError, TypeError) as e:
        logger.warning(f"デバイス情報パース失敗: {e}, data={data}")
        return None


def _map_drive_letters(devices: list[DeviceInfo]) -> None:
    """PhysicalDrive → ドライブレターのマッピング"""
    try:
        # diskdrive → partition → logical disk のチェーンを辿る
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_DiskDrive | ForEach-Object { "
             "$disk = $_; "
             "Get-CimAssociatedInstance -InputObject $disk -ResultClassName Win32_DiskPartition | ForEach-Object { "
             "$part = $_; "
             "Get-CimAssociatedInstance -InputObject $part -ResultClassName Win32_LogicalDisk | ForEach-Object { "
             "[PSCustomObject]@{Index=$disk.Index;Letter=$_.DeviceID;FS=$_.FileSystem;Size=$_.Size;Free=$_.FreeSpace} "
             "} } } | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15, encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0 or not result.stdout.strip():
            return

        mapping = json.loads(result.stdout)
        if isinstance(mapping, dict):
            mapping = [mapping]

        for m in mapping:
            idx = int(m.get("Index", -1))
            letter = m.get("Letter", "")
            for dev in devices:
                if dev.index == idx and letter:
                    dev.drive_letters.append(letter)
                    dev.partitions.append(PartitionInfo(
                        letter=letter,
                        file_system=m.get("FS", ""),
                        size_bytes=int(m.get("Size", 0) or 0),
                        free_bytes=int(m.get("Free", 0) or 0),
                    ))
    except Exception as e:
        logger.warning(f"ドライブレターマッピング失敗: {e}")


def _detect_system_drive(devices: list[DeviceInfo]) -> None:
    """システムドライブ（C:を含む）を判定"""
    for dev in devices:
        if "C:" in dev.drive_letters:
            dev.is_system_drive = True
            logger.info(f"システムドライブ: {dev.device_path} ({dev.model})")


def detect_optical_drives() -> list[OpticalDriveInfo]:
    """光学ドライブを列挙"""
    drives = []

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_CDROMDrive -ErrorAction SilentlyContinue | Select-Object Drive,Name,MediaLoaded,DeviceID | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15, encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:
            logger.error(f"光学ドライブ情報取得失敗: {result.stderr}")
            return drives

        stdout = result.stdout.strip()
        if not stdout:
            return drives
            
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.error(f"光学ドライブJSONパースエラー: {e}")
            return drives

        if isinstance(data, dict):
            # 単一ドライブの場合はリスト化
            data = [data]

        for i, item in enumerate(data):
            drive = _parse_optical_json(item, i)
            if drive:
                drives.append(drive)

        logger.info(f"光学ドライブ検出: {len(drives)} 台")

    except Exception as e:
        logger.error(f"光学ドライブ検出エラー: {e}")

    return drives


def _parse_optical_json(data: dict, index: int) -> Optional[OpticalDriveInfo]:
    """JSON出力を OpticalDriveInfo に変換"""
    try:
        drive_letter = str(data.get("Drive") or "").strip()
        media_loaded = bool(data.get("MediaLoaded"))

        return OpticalDriveInfo(
            device_path=f"\\\\.\\CdRom{index}",
            drive_letter=drive_letter,
            drive_model=str(data.get("Name") or "Unknown").strip(),
            media_loaded=media_loaded,
            media_type="NoMedia" if not media_loaded else "Unknown",
        )
    except Exception as e:
        logger.warning(f"光学ドライブ情報パース失敗: {e}")
        return None


def format_capacity(bytes_val: int) -> str:
    """バイト数を人間可読形式に変換"""
    if bytes_val <= 0:
        return "不明"
    units = [("TB", 1024**4), ("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)]
    for unit, divisor in units:
        if bytes_val >= divisor:
            return f"{bytes_val / divisor:.2f} {unit}"
    return f"{bytes_val} B"
