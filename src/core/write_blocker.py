"""
MFEPS v2.0 — ソフトウェアライトブロック
Windows レジストリ方式 + デバイス固有チェック
"""
import ctypes
import logging
import winreg
from typing import Optional

logger = logging.getLogger("mfeps.write_blocker")

STORAGE_POLICIES_KEY = r"SYSTEM\CurrentControlSet\Control\StorageDevicePolicies"


def enable_global_write_block() -> bool:
    """
    レジストリ方式でグローバルライトブロックを有効化。
    全USBストレージデバイスに影響。
    """
    try:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, STORAGE_POLICIES_KEY,
                                0, winreg.KEY_SET_VALUE)
        except FileNotFoundError:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, STORAGE_POLICIES_KEY)

        winreg.SetValueEx(key, "WriteProtect", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)

        logger.info("グローバルライトブロック: 有効化")
        return True

    except PermissionError:
        logger.error("グローバルライトブロック有効化失敗: 管理者権限が必要です")
        return False
    except Exception as e:
        logger.error(f"グローバルライトブロック有効化失敗: {e}")
        return False


def disable_global_write_block() -> bool:
    """グローバルライトブロックを解除"""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, STORAGE_POLICIES_KEY,
                             0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "WriteProtect", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)

        logger.info("グローバルライトブロック: 無効化")
        return True

    except FileNotFoundError:
        logger.info("グローバルライトブロック: レジストリキーが存在しません（既に無効）")
        return True
    except PermissionError:
        logger.error("グローバルライトブロック無効化失敗: 管理者権限が必要です")
        return False
    except Exception as e:
        logger.error(f"グローバルライトブロック無効化失敗: {e}")
        return False


def is_global_write_blocked() -> bool:
    """グローバルライトブロックが有効か確認"""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, STORAGE_POLICIES_KEY,
                             0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "WriteProtect")
        winreg.CloseKey(key)
        return value == 1
    except (FileNotFoundError, OSError):
        return False


def check_write_protection(device_path: str) -> dict:
    """
    指定デバイスの書込保護状態を総合チェック。
    Returns: {
        "hardware_blocked": bool,  — ハードウェアライトブロッカー検出
        "software_blocked": bool,  — ソフトウェアライトブロック適用中
        "registry_blocked": bool,  — レジストリ方式ライトブロック
        "is_protected": bool,      — いずれかで保護されている
    }
    """
    result = {
        "hardware_blocked": False,
        "software_blocked": False,
        "registry_blocked": is_global_write_blocked(),
        "is_protected": False,
    }

    try:
        from src.core.win32_raw_io import open_device, is_writable, close_device
        handle = open_device(device_path)
        try:
            writable = is_writable(handle)
            if not writable:
                result["hardware_blocked"] = True
        except Exception:
            # IOCTL_DISK_IS_WRITABLE がエラーを返す場合、ブロックされている可能性
            result["hardware_blocked"] = True
        finally:
            close_device(handle)
    except Exception as e:
        logger.warning(f"デバイス書込保護チェック失敗: {e}")

    result["is_protected"] = (result["hardware_blocked"] or
                              result["software_blocked"] or
                              result["registry_blocked"])

    return result


def verify_write_block(device_path: str) -> bool:
    """
    ライトブロックが有効であることを検証。
    1バイトの書込を試行し、失敗（拒否）されれば True（保護されている）。
    """
    try:
        kernel32 = ctypes.windll.kernel32

        # 書込モードでオープンを試行
        GENERIC_WRITE = 0x40000000
        handle = kernel32.CreateFileW(
            device_path,
            GENERIC_WRITE,
            0x00000001 | 0x00000002,  # FILE_SHARE_READ | FILE_SHARE_WRITE
            None,
            3,  # OPEN_EXISTING
            0,
            None,
        )

        if handle == -1:
            # オープン失敗 = 書込拒否 = 保護されている
            logger.info(f"ライトブロック検証 OK: {device_path} (書込オープン拒否)")
            return True

        # オープンできてしまった = 保護されていない
        kernel32.CloseHandle(handle)
        logger.warning(f"ライトブロック検証 NG: {device_path} (書込オープン成功)")
        return False

    except Exception as e:
        logger.error(f"ライトブロック検証エラー: {e}")
        return False


def get_protection_badge(status: dict) -> tuple[str, str, str]:
    """
    保護状態からバッジ情報を返す。
    Returns: (text, color, icon)
    """
    if status["hardware_blocked"]:
        return "HW保護済", "positive", "shield"
    elif status["registry_blocked"]:
        return "SW保護済", "warning", "security"
    elif status["is_protected"]:
        return "保護済", "positive", "lock"
    else:
        return "未保護", "negative", "lock_open"
