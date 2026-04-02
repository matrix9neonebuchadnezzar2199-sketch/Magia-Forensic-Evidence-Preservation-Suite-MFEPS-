"""CFTT リファレンス検証テスト — 共通フィクスチャ"""
import json
from pathlib import Path

import pytest

REFERENCE_DIR = Path(__file__).parent / "reference"
REFERENCE_HASHES_FILE = REFERENCE_DIR / "reference_hashes.json"


@pytest.fixture
def reference_hashes():
    """リファレンスハッシュ辞書を返す。ファイルが無ければスキップ。"""
    if not REFERENCE_HASHES_FILE.exists():
        pytest.skip("reference_hashes.json が未配置です")
    with open(REFERENCE_HASHES_FILE, encoding="utf-8") as f:
        return json.load(f)
