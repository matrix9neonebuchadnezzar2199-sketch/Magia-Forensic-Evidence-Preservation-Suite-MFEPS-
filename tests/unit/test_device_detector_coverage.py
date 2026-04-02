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
