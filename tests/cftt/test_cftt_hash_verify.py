"""
NIST CFTT 準拠ハッシュ検証テスト。
reference_hashes.json のエントリごとに、既存イメージファイルのハッシュを再計算し、
リファレンス値と一致するかを検証する。
"""
from pathlib import Path

import pytest

from src.core.hash_engine import verify_image_hash


@pytest.mark.cftt
class TestCFTTHashVerify:

    def test_reference_images_exist(self, reference_hashes):
        """リファレンスに記載された全イメージファイルが存在するか"""
        for name, entry in reference_hashes.items():
            if name.startswith("_"):
                continue
            img_path = entry.get("image_path", "")
            if img_path:
                assert Path(img_path).exists(), (
                    f"リファレンスイメージ不在: {name} → {img_path}"
                )

    @pytest.mark.parametrize("algo", ["md5", "sha256"])
    def test_hash_matches_reference(self, reference_hashes, algo):
        """各イメージのハッシュがリファレンスと一致"""
        for name, entry in reference_hashes.items():
            if name.startswith("_"):
                continue
            expected = entry.get(algo, "")
            if not expected:
                continue
            img_path = entry.get("image_path", "")
            if not img_path or not Path(img_path).exists():
                pytest.skip(f"イメージ不在: {img_path}")

            result = verify_image_hash(
                image_path=img_path,
                expected={algo: expected},
            )
            assert result["all_match"], (
                f"CFTT 検証失敗: {name}/{algo} "
                f"expected={expected}, "
                f"got={result.get('computed', {}).get(algo, 'N/A')}"
            )

    def test_byte_count_matches(self, reference_hashes):
        """イメージファイルサイズがリファレンスの total_bytes と一致"""
        for name, entry in reference_hashes.items():
            if name.startswith("_"):
                continue
            img_path = entry.get("image_path", "")
            expected_bytes = entry.get("total_bytes", 0)
            if not img_path or not expected_bytes:
                continue
            if not Path(img_path).exists():
                pytest.skip(f"イメージ不在: {img_path}")

            actual = Path(img_path).stat().st_size
            assert actual == expected_bytes, (
                f"CFTT バイト数不一致: {name} "
                f"expected={expected_bytes}, actual={actual}"
            )
