"""CFTT リファレンス検証テスト — 共通フィクスチャ"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

REFERENCE_DIR = Path(__file__).parent / "reference"
REFERENCE_HASHES_FILE = REFERENCE_DIR / "reference_hashes.json"

REFERENCE_SIZE = 128 * 1024  # 128 KiB
SECTOR_SIZE = 512


@pytest.fixture
def reference_hashes():
    """リファレンスハッシュ辞書を返す。ファイルが無ければスキップ。"""
    if not REFERENCE_HASHES_FILE.exists():
        pytest.skip("reference_hashes.json が未配置です")
    with open(REFERENCE_HASHES_FILE, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def reference_image(tmp_path) -> dict:
    """128 KiB のリファレンスバイナリを生成し、SHA-256 を事前計算。"""
    data = os.urandom(REFERENCE_SIZE)
    path = tmp_path / "reference.bin"
    path.write_bytes(data)
    sha256 = hashlib.sha256(data).hexdigest()
    md5 = hashlib.md5(data).hexdigest()
    sha1 = hashlib.sha1(data).hexdigest()
    return {
        "path": path,
        "data": data,
        "size": REFERENCE_SIZE,
        "sha256": sha256,
        "md5": md5,
        "sha1": sha1,
        "sector_count": REFERENCE_SIZE // SECTOR_SIZE,
    }


@pytest.fixture
def reference_with_bad_sectors(tmp_path) -> dict:
    """不良セクタ（セクタ 10, 20）をマークするリファレンス（データは通常バイト）。"""
    data = bytearray(os.urandom(REFERENCE_SIZE))
    bad_sectors = [10, 20]
    path = tmp_path / "reference_bad.bin"
    path.write_bytes(bytes(data))
    return {
        "path": path,
        "data": bytes(data),
        "size": REFERENCE_SIZE,
        "bad_sectors": bad_sectors,
    }
