"""
MFEPS v2.1.0 — Win32 RAW I/O ラッパー
ctypes 経由で Windows Kernel32 / DeviceIoControl を操作
"""
import ctypes
import ctypes.wintypes as wintypes
import logging
from typing import Optional

from src.utils.constants import (
    GENERIC_READ, FILE_SHARE_READ, FILE_SHARE_WRITE, OPEN_EXISTING,
    FILE_FLAG_NO_BUFFERING, FILE_FLAG_SEQUENTIAL_SCAN, INVALID_HANDLE_VALUE,
    IOCTL_DISK_GET_DRIVE_GEOMETRY, IOCTL_DISK_GET_LENGTH_INFO,
    IOCTL_DISK_IS_WRITABLE,
    IOCTL_CDROM_READ_TOC, IOCTL_CDROM_READ_TOC_EX, IOCTL_CDROM_RAW_READ,
    IOCTL_SCSI_PASS_THROUGH_DIRECT,
)
from src.utils.error_codes import E2003, E2004, E3001

logger = logging.getLogger("mfeps.win32_raw_io")

kernel32 = ctypes.windll.kernel32

# ===== ctypes 構造体 =====

class DISK_GEOMETRY(ctypes.Structure):
    _fields_ = [
        ("Cylinders", ctypes.c_longlong),
        ("MediaType", ctypes.c_int),
        ("TracksPerCylinder", wintypes.DWORD),
        ("SectorsPerTrack", wintypes.DWORD),
        ("BytesPerSector", wintypes.DWORD),
    ]


class GET_LENGTH_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.c_longlong),
    ]


class TRACK_DATA(ctypes.Structure):
    _fields_ = [
        ("Reserved", ctypes.c_ubyte),
        ("Control_Adr", ctypes.c_ubyte),
        ("TrackNumber", ctypes.c_ubyte),
        ("Reserved1", ctypes.c_ubyte),
        ("Address", ctypes.c_ubyte * 4),
    ]


class CDROM_TOC(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.WORD),
        ("FirstTrack", ctypes.c_ubyte),
        ("LastTrack", ctypes.c_ubyte),
        ("TrackData", TRACK_DATA * 100),
    ]


class SCSI_PASS_THROUGH_DIRECT(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.c_ushort),
        ("ScsiStatus", ctypes.c_ubyte),
        ("PathId", ctypes.c_ubyte),
        ("TargetId", ctypes.c_ubyte),
        ("Lun", ctypes.c_ubyte),
        ("CdbLength", ctypes.c_ubyte),
        ("SenseInfoLength", ctypes.c_ubyte),
        ("DataIn", ctypes.c_ubyte),
        ("DataTransferLength", ctypes.c_ulong),
        ("TimeOutValue", ctypes.c_ulong),
        ("DataBuffer", ctypes.c_void_p),
        ("SenseInfoOffset", ctypes.c_ulong),
        ("Cdb", ctypes.c_ubyte * 16),
    ]


# ===== 関数群 =====

def open_device(path: str) -> int:
    """デバイスをRAW読取モードでオープン（管理者権限必須）"""
    handle = kernel32.CreateFileW(
        path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_NO_BUFFERING | FILE_FLAG_SEQUENTIAL_SCAN,
        None,
    )
    if handle == INVALID_HANDLE_VALUE:
        error_code = kernel32.GetLastError()
        if error_code == 5:  # ACCESS_DENIED
            raise OSError(f"{E2003} (Win32 Error: {error_code}) Path: {path}")
        raise OSError(f"{E3001} (Win32 Error: {error_code}) Path: {path}")

    logger.info(f"デバイスオープン: {path} (handle={handle})")
    return handle


def close_device(handle: int) -> None:
    """デバイスハンドルをクローズ"""
    if handle and handle != INVALID_HANDLE_VALUE:
        kernel32.CloseHandle(handle)
        logger.debug(f"デバイスクローズ: handle={handle}")


def get_disk_geometry(handle: int) -> dict:
    """ディスクジオメトリ取得"""
    geo = DISK_GEOMETRY()
    bytes_returned = wintypes.DWORD(0)

    success = kernel32.DeviceIoControl(
        handle,
        IOCTL_DISK_GET_DRIVE_GEOMETRY,
        None, 0,
        ctypes.byref(geo), ctypes.sizeof(geo),
        ctypes.byref(bytes_returned),
        None,
    )
    if not success:
        error_code = kernel32.GetLastError()
        raise OSError(f"{E2004} (Win32 Error: {error_code})")

    result = {
        "cylinders": geo.Cylinders,
        "media_type": geo.MediaType,
        "tracks_per_cylinder": geo.TracksPerCylinder,
        "sectors_per_track": geo.SectorsPerTrack,
        "bytes_per_sector": geo.BytesPerSector,
        "total_sectors": (geo.Cylinders * geo.TracksPerCylinder *
                          geo.SectorsPerTrack),
    }
    logger.debug(f"ディスクジオメトリ: {result}")
    return result


def get_disk_length(handle: int) -> int:
    """ディスク総バイト数を取得"""
    length_info = GET_LENGTH_INFORMATION()
    bytes_returned = wintypes.DWORD(0)

    success = kernel32.DeviceIoControl(
        handle,
        IOCTL_DISK_GET_LENGTH_INFO,
        None, 0,
        ctypes.byref(length_info), ctypes.sizeof(length_info),
        ctypes.byref(bytes_returned),
        None,
    )
    if not success:
        error_code = kernel32.GetLastError()
        raise OSError(f"ディスク長取得失敗 (Win32 Error: {error_code})")

    length = length_info.Length
    logger.debug(f"ディスク長: {length} bytes ({length / (1024**3):.2f} GiB)")
    return length


def is_writable(handle: int) -> bool:
    """デバイスが書込可能か判定"""
    bytes_returned = wintypes.DWORD(0)
    result = kernel32.DeviceIoControl(
        handle,
        IOCTL_DISK_IS_WRITABLE,
        None, 0,
        None, 0,
        ctypes.byref(bytes_returned),
        None,
    )
    return bool(result)


def read_sectors(handle: int, offset: int, size: int,
                 buffer: Optional[ctypes.Array] = None) -> bytes:
    """
    セクタアラインドリード。
    offset: 読取開始バイトオフセット（セクタ境界であること）
    size: 読取バイト数（セクタサイズの倍数であること）
    """
    # オフセット移動
    li = ctypes.c_longlong(offset)
    new_pos = ctypes.c_longlong(0)
    kernel32.SetFilePointerEx(handle, li, ctypes.byref(new_pos), 0)

    # バッファ確保（事前確保バッファは size 以下であること）
    if buffer is None:
        buffer = ctypes.create_string_buffer(size)
    elif ctypes.sizeof(buffer) < size:
        logger.debug(
            "read_sectors: バッファ不足 sizeof=%s need=%s — 新規確保",
            ctypes.sizeof(buffer),
            size,
        )
        buffer = ctypes.create_string_buffer(size)

    bytes_read = wintypes.DWORD(0)
    success = kernel32.ReadFile(
        handle, buffer, size,
        ctypes.byref(bytes_read), None,
    )
    if not success:
        error_code = kernel32.GetLastError()
        if error_code == 23:  # ERROR_CRC — 不良セクタ
            logger.warning(f"CRC エラー: offset={offset}, code={error_code}")
            return b'\x00' * size  # ゼロフィル
        raise OSError(f"読取エラー: offset={offset} (Win32 Error: {error_code})")

    return buffer.raw[:bytes_read.value]


def read_cdrom_toc(handle: int) -> dict:
    """光学ドライブ TOC 読取"""
    toc = CDROM_TOC()
    bytes_returned = wintypes.DWORD(0)

    success = kernel32.DeviceIoControl(
        handle,
        IOCTL_CDROM_READ_TOC_EX,
        None, 0,
        ctypes.byref(toc), ctypes.sizeof(toc),
        ctypes.byref(bytes_returned),
        None,
    )
    if not success:
        # フォールバック: 通常 TOC 読取
        success = kernel32.DeviceIoControl(
            handle,
            IOCTL_CDROM_READ_TOC,
            None, 0,
            ctypes.byref(toc), ctypes.sizeof(toc),
            ctypes.byref(bytes_returned),
            None,
        )
        if not success:
            error_code = kernel32.GetLastError()
            raise OSError(f"TOC 読取失敗 (Win32 Error: {error_code})")

    tracks = []
    n_data = toc.LastTrack - toc.FirstTrack + 1
    for i in range(n_data):
        td = toc.TrackData[i]
        addr = (td.Address[0] << 24 | td.Address[1] << 16 |
                td.Address[2] << 8 | td.Address[3])
        tracks.append({
            "track_number": td.TrackNumber,
            "control": td.Control_Adr >> 4,
            "adr": td.Control_Adr & 0x0F,
            "address_lba": addr,
            "is_data": bool((td.Control_Adr >> 4) & 0x04),
        })

    # リードアウト（トラック 0xAA）— MS CDROM_TOC では LastTrack の次エントリ
    leadout_idx = n_data
    if leadout_idx < 100:
        td = toc.TrackData[leadout_idx]
        addr = (td.Address[0] << 24 | td.Address[1] << 16 |
                td.Address[2] << 8 | td.Address[3])
        tracks.append({
            "track_number": 0xAA,
            "control": td.Control_Adr >> 4,
            "adr": td.Control_Adr & 0x0F,
            "address_lba": addr,
            "is_data": True,
        })

    result = {
        "first_track": toc.FirstTrack,
        "last_track": toc.LastTrack,
        "track_count": len(tracks),
        "tracks": tracks,
    }
    logger.debug(f"TOC: {result['track_count']} tracks")
    return result


def scsi_read_cd(handle: int, lba: int, sector_count: int,
                 sector_size: int = 2048) -> bytes:
    """
    SCSI READ CD コマンド (CDB 0xBE) 経由で光学メディアRAWセクタ読取。
    CD-DA: sector_size=2352, Data: sector_size=2048
    """
    total_size = sector_count * sector_size
    data_buffer = ctypes.create_string_buffer(total_size)

    sptd = SCSI_PASS_THROUGH_DIRECT()
    sptd.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
    sptd.CdbLength = 12
    sptd.DataIn = 1  # SCSI_IOCTL_DATA_IN
    sptd.DataTransferLength = total_size
    sptd.DataBuffer = ctypes.cast(data_buffer, ctypes.c_void_p)
    sptd.TimeOutValue = 30
    sptd.SenseInfoLength = 0
    sptd.SenseInfoOffset = 0

    # CDB: READ CD (0xBE)
    sptd.Cdb[0] = 0xBE
    # Expected Sector Type
    if sector_size == 2352:
        sptd.Cdb[1] = 0x04  # CD-DA
    else:
        sptd.Cdb[1] = 0x08  # Mode 1
    # Starting LBA (big-endian)
    sptd.Cdb[2] = (lba >> 24) & 0xFF
    sptd.Cdb[3] = (lba >> 16) & 0xFF
    sptd.Cdb[4] = (lba >> 8) & 0xFF
    sptd.Cdb[5] = lba & 0xFF
    # Transfer Length (big-endian)
    sptd.Cdb[6] = (sector_count >> 16) & 0xFF
    sptd.Cdb[7] = (sector_count >> 8) & 0xFF
    sptd.Cdb[8] = sector_count & 0xFF
    # Flags
    if sector_size == 2352:
        sptd.Cdb[9] = 0xF8  # Sync + Header + SubHeader + UserData
    else:
        sptd.Cdb[9] = 0x10  # User Data only

    bytes_returned = wintypes.DWORD(0)
    success = kernel32.DeviceIoControl(
        handle,
        IOCTL_SCSI_PASS_THROUGH_DIRECT,
        ctypes.byref(sptd), ctypes.sizeof(sptd),
        ctypes.byref(sptd), ctypes.sizeof(sptd),
        ctypes.byref(bytes_returned),
        None,
    )
    if not success:
        error_code = kernel32.GetLastError()
        raise OSError(f"SCSI READ CD 失敗: LBA={lba} (Win32 Error: {error_code})")

    return data_buffer.raw[:total_size]
