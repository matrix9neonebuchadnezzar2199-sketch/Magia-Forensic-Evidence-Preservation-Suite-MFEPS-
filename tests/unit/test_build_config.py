"""ポータブルビルド用設定テスト"""
import sys
from pathlib import Path

from src.utils.config import MFEPSConfig, _get_base_dir


def test_base_dir_normal():
    cfg = MFEPSConfig()
    assert cfg.base_dir.is_dir()


def test_base_dir_frozen(tmp_path, monkeypatch):
    fake_exe = tmp_path / "MFEPS.exe"
    fake_exe.touch()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    assert _get_base_dir() == tmp_path


def test_locales_dir_exists():
    locales = (
        Path(__file__).resolve().parent.parent.parent / "src" / "locales"
    )
    assert locales.is_dir()
