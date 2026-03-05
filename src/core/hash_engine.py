"""
MFEPS v2.0 — トリプルハッシュエンジン
MD5 + SHA-1 + SHA-256 ストリーミング同時計算
"""
import hashlib
import logging
from typing import Callable, Optional
from pathlib import Path

logger = logging.getLogger("mfeps.hash_engine")


class TripleHashEngine:
    """
    MD5, SHA-1, SHA-256 を同時更新するストリーミングハッシュエンジン。
    hashlib 内部は C(OpenSSL) 実装のため、3アルゴリズム合計で ~800 MiB/s 以上の処理能力。
    """

    def __init__(self):
        self._md5 = hashlib.md5()
        self._sha1 = hashlib.sha1()
        self._sha256 = hashlib.sha256()
        self._bytes_processed = 0

    def update(self, data: bytes) -> None:
        """3つのハッシュを同時更新"""
        self._md5.update(data)
        self._sha1.update(data)
        self._sha256.update(data)
        self._bytes_processed += len(data)

    def hexdigests(self) -> dict[str, str]:
        """現在のハッシュ値を16進文字列で返す"""
        return {
            "md5": self._md5.hexdigest(),
            "sha1": self._sha1.hexdigest(),
            "sha256": self._sha256.hexdigest(),
        }

    @property
    def bytes_processed(self) -> int:
        return self._bytes_processed

    def reset(self) -> None:
        """新規イメージ用にリセット"""
        self._md5 = hashlib.md5()
        self._sha1 = hashlib.sha1()
        self._sha256 = hashlib.sha256()
        self._bytes_processed = 0

    def copy(self) -> "TripleHashEngine":
        """現在の状態をコピー（中断・再開用）"""
        new = TripleHashEngine()
        new._md5 = self._md5.copy()
        new._sha1 = self._sha1.copy()
        new._sha256 = self._sha256.copy()
        new._bytes_processed = self._bytes_processed
        return new


def verify_image_hash(
    image_path: str | Path,
    expected: dict[str, str],
    buffer_size: int = 1_048_576,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """
    出力イメージファイルを再読取してトリプルハッシュを計算し、期待値と比較。
    Returns: {
        "md5_match": bool,
        "sha1_match": bool,
        "sha256_match": bool,
        "all_match": bool,
        "computed": {"md5": str, "sha1": str, "sha256": str},
    }
    """
    engine = TripleHashEngine()
    file_path = Path(image_path)
    file_size = file_path.stat().st_size

    logger.info(f"イメージ検証開始: {file_path} ({file_size} bytes)")

    with open(file_path, "rb") as f:
        while True:
            data = f.read(buffer_size)
            if not data:
                break
            engine.update(data)

            if progress_callback:
                progress_callback(engine.bytes_processed, file_size)

    computed = engine.hexdigests()

    result = {
        "md5_match": computed["md5"] == expected.get("md5", ""),
        "sha1_match": computed["sha1"] == expected.get("sha1", ""),
        "sha256_match": computed["sha256"] == expected.get("sha256", ""),
        "computed": computed,
    }
    result["all_match"] = (result["md5_match"] and
                           result["sha1_match"] and
                           result["sha256_match"])

    if result["all_match"]:
        logger.info("イメージ検証: ✅ 全ハッシュ一致")
    else:
        logger.error("イメージ検証: ❌ ハッシュ不一致")
        for algo in ["md5", "sha1", "sha256"]:
            if not result[f"{algo}_match"]:
                logger.error(
                    f"  {algo}: expected={expected.get(algo, 'N/A')}, "
                    f"computed={computed[algo]}")

    return result
