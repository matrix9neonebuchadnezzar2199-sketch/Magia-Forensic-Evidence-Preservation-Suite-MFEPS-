"""CFTT フレームワーク（JSON / スキップ）の単体検証"""
import json


from tests.cftt.conftest import REFERENCE_HASHES_FILE


def test_reference_json_schema(tmp_path):
    sample = {
        "_comment": "x",
        "case1": {
            "source_path": "s",
            "image_path": str(tmp_path / "img.bin"),
            "total_bytes": 3,
            "md5": "a" * 32,
            "sha256": "b" * 64,
        },
    }
    p = tmp_path / "ref.json"
    p.write_text(json.dumps(sample), encoding="utf-8")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    assert "case1" in data
    assert len(data["case1"]["md5"]) == 32


def test_reference_hashes_path_is_configured():
    """CFTT 用 reference ファイルパスが定義されていること。"""
    assert REFERENCE_HASHES_FILE.name == "reference_hashes.json"
