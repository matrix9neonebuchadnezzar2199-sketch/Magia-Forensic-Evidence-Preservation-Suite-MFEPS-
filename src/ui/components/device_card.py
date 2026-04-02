"""
MFEPS v2.1.0 — デバイスカード UIコンポーネント
サイドバー内に表示するデバイス情報カード
"""
from nicegui import ui
from src.core.device_detector import DeviceInfo, OpticalDriveInfo, format_capacity
from src.core.write_blocker import check_write_protection, get_protection_badge


def render_block_device_card(device: DeviceInfo, on_click=None):
    """USB/HDD デバイスカードを描画"""
    # システムドライブ判定
    is_system = device.is_system_drive
    border_color = "#FF5252" if is_system else "rgba(108, 99, 255, 0.3)"

    with ui.card().classes("q-pa-sm q-mb-xs cursor-pointer full-width").style(
            f"border-left: 3px solid {border_color};"):

        if on_click and not is_system:
            ui.card().on("click", lambda d=device: on_click(d))

        # 上段: アイコン + デバイス名
        with ui.row().classes("items-center gap-2"):
            icon = "usb" if "USB" in device.interface_type.upper() else "hard_drive"
            ui.icon(icon).classes("text-lg")
            ui.label(device.device_path.replace("\\\\.\\", "")).classes(
                "text-weight-bold text-body2")

        # 中段: モデル・シリアル・容量
        ui.label(device.model).classes("text-caption text-grey-5 q-ml-lg")

        with ui.row().classes("q-ml-lg gap-2 items-center"):
            if device.serial:
                ui.label(f"S/N: {device.serial[:20]}").classes("text-caption text-grey-6")
            ui.label(f"| {format_capacity(device.capacity_bytes)}").classes(
                "text-caption text-grey-5")

        # ドライブレター
        if device.drive_letters:
            with ui.row().classes("q-ml-lg gap-1"):
                for letter in device.drive_letters:
                    ui.badge(letter, color="primary").props("dense outline")

        # 下段: システムドライブ警告 or ライトブロック状態
        if is_system:
            ui.badge("SYSTEM DRIVE — 操作不可", color="negative").classes(
                "q-mt-xs q-ml-lg").props("dense")
        else:
            # ライトブロック状態（簡易版）
            with ui.row().classes("q-ml-lg q-mt-xs items-center gap-1"):
                protection = check_write_protection(device.device_path) if not is_system else {}
                text, color, icon_name = get_protection_badge(protection) if protection else ("確認中", "grey", "help")
                ui.icon(icon_name, size="xs", color=color)
                ui.label(text).classes(f"text-caption text-{color}")


def render_optical_drive_card(drive: OpticalDriveInfo, on_click=None):
    """光学ドライブカードを描画"""

    with ui.card().classes("q-pa-sm q-mb-xs cursor-pointer full-width").style(
            "border-left: 3px solid rgba(108, 99, 255, 0.3);"):

        if on_click and drive.media_loaded:
            ui.card().on("click", lambda d=drive: on_click(d))

        # 上段
        with ui.row().classes("items-center gap-2"):
            ui.icon("album").classes("text-lg")
            ui.label(f"{drive.drive_letter} ({drive.device_path.replace(chr(92)*4+'.'+chr(92), '')})").classes(
                "text-weight-bold text-body2")

        # モデル
        ui.label(drive.drive_model).classes("text-caption text-grey-5 q-ml-lg")

        # メディア状態
        with ui.row().classes("q-ml-lg q-mt-xs items-center gap-1"):
            if drive.media_loaded:
                ui.icon("check_circle", size="xs", color="positive")
                ui.label(f"メディア: {drive.media_type}").classes("text-caption text-positive")
            else:
                ui.icon("eject", size="xs", color="grey")
                ui.label("メディア未挿入").classes("text-caption text-grey-6")
