"""device_detector 追加カバレッジ"""
import subprocess
from unittest.mock import MagicMock

import src.core.device_detector as device_detector
from src.core.device_detector import (
    _parse_device_json,
    _parse_optical_json,
    DeviceInfo,
    detect_block_devices,
    detect_optical_drives,
    storage_interface_icon,
    storage_interface_label,
)


def test_parse_device_json_invalid_index():
    assert _parse_device_json({"Index": None}) is None
    assert _parse_device_json({"Index": -1}) is None


def test_parse_device_json_ok():
    d = _parse_device_json(
        {
            "Index": 2,
            "Model": "Disk",
            "SerialNumber": "ABC",
            "Size": 1000,
            "MediaType": "Fixed",
            "InterfaceType": "SATA",
            "BytesPerSector": 512,
        }
    )
    assert d is not None
    assert d.index == 2
    assert "PhysicalDrive2" in d.device_path


def test_parse_optical_json():
    o = _parse_optical_json({"Drive": "D:", "Name": "Opti", "MediaLoaded": True}, 0)
    assert o is not None
    assert o.drive_letter == "D:"
    assert o.media_loaded is True


def test_detect_system_drive_flag():
    d = DeviceInfo(index=0, drive_letters=["C:", "D:"])
    device_detector._detect_system_drive([d])
    assert d.is_system_drive is True


def test_detect_block_devices_bad_returncode(monkeypatch):
    def fake_run(*_a, **_k):
        return MagicMock(returncode=1, stdout="", stderr="e")

    monkeypatch.setattr(device_detector.subprocess, "run", fake_run)
    assert detect_block_devices() == []


def test_detect_block_devices_empty_stdout(monkeypatch):
    def fake_run(*_a, **_k):
        return MagicMock(returncode=0, stdout="  \n", stderr="")

    monkeypatch.setattr(device_detector.subprocess, "run", fake_run)
    assert detect_block_devices() == []


def test_detect_block_devices_bad_json(monkeypatch):
    def fake_run(*_a, **_k):
        return MagicMock(returncode=0, stdout="not-json", stderr="")

    monkeypatch.setattr(device_detector.subprocess, "run", fake_run)
    assert detect_block_devices() == []


def test_detect_block_devices_success(monkeypatch):
    json_line = (
        '{"Index":0,"Model":"M","SerialNumber":"","Size":2048,'
        '"MediaType":"Fixed","InterfaceType":"SCSI","BytesPerSector":512,"Partitions":1}'
    )
    calls = {"n": 0}

    def fake_run(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return MagicMock(returncode=0, stdout=json_line, stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(device_detector.subprocess, "run", fake_run)
    devs = detect_block_devices()
    assert len(devs) == 1
    assert devs[0].model == "M"


def test_detect_optical_bad_return(monkeypatch):
    def fake_run(*_a, **_k):
        return MagicMock(returncode=1, stdout="", stderr="x")

    monkeypatch.setattr(device_detector.subprocess, "run", fake_run)
    assert detect_optical_drives() == []


def test_detect_optical_bad_json(monkeypatch):
    def fake_run(*_a, **_k):
        return MagicMock(returncode=0, stdout="{", stderr="")

    monkeypatch.setattr(device_detector.subprocess, "run", fake_run)
    assert detect_optical_drives() == []


def test_detect_optical_one_drive(monkeypatch):
    json_line = '{"Drive":"E:","Name":"DVD","MediaLoaded":false}'
    calls = {"n": 0}

    def fake_run(*_a, **_k):
        calls["n"] += 1
        return MagicMock(returncode=0, stdout=json_line, stderr="")

    monkeypatch.setattr(device_detector.subprocess, "run", fake_run)
    drives = detect_optical_drives()
    assert len(drives) == 1
    assert drives[0].drive_letter == "E:"


def test_detect_block_timeout(monkeypatch):
    def fake_run(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="powershell", timeout=1)

    monkeypatch.setattr(device_detector.subprocess, "run", fake_run)
    assert detect_block_devices() == []


def test_detect_block_generic_error(monkeypatch):
    def fake_run(*_a, **_k):
        raise OSError("fail")

    monkeypatch.setattr(device_detector.subprocess, "run", fake_run)
    assert detect_block_devices() == []


def test_detect_block_with_letter_mapping(monkeypatch):
    disk = (
        '{"Index":0,"Model":"M","SerialNumber":"","Size":1000,'
        '"MediaType":"Fixed","InterfaceType":"IDE","BytesPerSector":512,"Partitions":1}'
    )
    mapping = (
        '[{"Index":0,"Letter":"C:","FS":"NTFS","Size":1000,"Free":500}]'
    )
    n = {"c": 0}

    def fake_run(*_a, **_k):
        n["c"] += 1
        if n["c"] == 1:
            return MagicMock(returncode=0, stdout=disk, stderr="")
        return MagicMock(returncode=0, stdout=mapping, stderr="")

    monkeypatch.setattr(device_detector.subprocess, "run", fake_run)
    devs = detect_block_devices()
    assert devs[0].drive_letters == ["C:"]
    assert devs[0].is_system_drive is True


def test_parse_device_json_bad_values():
    assert _parse_device_json({"Index": 0, "Size": "not-int"}) is None


def test_detect_optical_exception(monkeypatch):
    def fake_run(*_a, **_k):
        raise RuntimeError("x")

    monkeypatch.setattr(device_detector.subprocess, "run", fake_run)
    assert detect_optical_drives() == []


def test_parse_optical_json_failure():
    class BadMedia:
        def __bool__(self):
            raise ValueError("bad")

    assert _parse_optical_json({"Drive": "D:", "MediaLoaded": BadMedia()}, 0) is None


def test_storage_interface_nvme_vs_usb():
    nvme = DeviceInfo(
        index=2,
        model="NVMe PC801 NVMe SK hy",
        interface_type="SCSI",
        media_type="Fixed hard disk media",
    )
    assert storage_interface_icon(nvme) == "memory"
    assert "NVMe" in storage_interface_label(nvme)

    usb_disk = DeviceInfo(
        index=3,
        model="SanDisk Ultra",
        interface_type="USB",
        media_type="Removable Media",
    )
    assert storage_interface_icon(usb_disk) == "usb"
    assert "USB" in storage_interface_label(usb_disk)


def test_storage_interface_label_fallback():
    empty = DeviceInfo(index=0, model="", interface_type="", media_type="")
    assert storage_interface_label(empty) == "—"


def test_storage_interface_label_branches():
    sata_hdd = DeviceInfo(
        index=0,
        model="WDC WD10EZEX",
        interface_type="IDE",
        media_type="Fixed hard disk media",
    )
    assert "SATA HDD" in storage_interface_label(sata_hdd)
    assert storage_interface_icon(sata_hdd) == "hard_drive"

    sata_ssd = DeviceInfo(
        index=1,
        model="Samsung SSD 860",
        interface_type="IDE",
        media_type="Fixed",
    )
    assert "SATA SSD" in storage_interface_label(sata_ssd)

    scsi_ssd = DeviceInfo(
        index=2,
        model="Samsung SSD 870",
        interface_type="SCSI",
        media_type="Fixed",
    )
    assert "SATA SSD" in storage_interface_label(scsi_ssd)

    usb_nvme = DeviceInfo(
        index=3,
        model="NVMe Enclosure",
        interface_type="USB",
        media_type="Fixed",
    )
    assert "USB（NVMe" in storage_interface_label(usb_nvme)
    assert storage_interface_icon(usb_nvme) == "usb"

    removable = DeviceInfo(
        index=4,
        model="Flash",
        interface_type="USB",
        media_type="Removable Media",
    )
    assert storage_interface_label(removable).startswith("USB")
