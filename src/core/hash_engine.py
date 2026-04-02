"""
MFEPS v2.1.0 — トリプルハッシュエンジン
MD5 + SHA-1 + SHA-256（＋オプション SHA-512）ストリーミング同時計算
"""
import hashlib
import logging
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("mfeps.hash_engine")


class TripleHashEngine:
    """
    複数アルゴリズムを同時更新するストリーミングハッシュエンジン。
    既定は MD5 + SHA-1 + SHA-256。SHA-512 は設定で有効化。
    """

    def __init__(
        self,
        *,
        md5: bool = True,
        sha1: bool = True,
        sha256: bool = True,
        sha512: bool = False,
    ):
        self._md5 = hashlib.md5() if md5 else None
        self._sha1 = hashlib.sha1() if sha1 else None
        self._sha256 = hashlib.sha256() if sha256 else None
        self._sha512 = hashlib.sha512() if sha512 else None
        self._bytes_processed = 0
        self._enabled = {"md5": md5, "sha1": sha1, "sha256": sha256, "sha512": sha512}

    def update(self, data: bytes) -> None:
        """有効なハッシュを同時更新"""
        if self._md5:
            self._md5.update(data)
        if self._sha1:
            self._sha1.update(data)
        if self._sha256:
            self._sha256.update(data)
        if self._sha512:
            self._sha512.update(data)
        self._bytes_processed += len(data)

    def hexdigests(self) -> dict[str, str]:
        """現在のハッシュ値を16進文字列で返す（有効なもののみ）"""
        out: dict[str, str] = {}
        if self._md5:
            out["md5"] = self._md5.hexdigest()
        if self._sha1:
            out["sha1"] = self._sha1.hexdigest()
        if self._sha256:
            out["sha256"] = self._sha256.hexdigest()
        if self._sha512:
            out["sha512"] = self._sha512.hexdigest()
        return out

    @property
    def bytes_processed(self) -> int:
        return self._bytes_processed

    def reset(self) -> None:
        """新規イメージ用にリセット"""
        md5, sha1, sha256, sha512 = (
            self._enabled["md5"],
            self._enabled["sha1"],
            self._enabled["sha256"],
            self._enabled["sha512"],
        )
        self.__init__(md5=md5, sha1=sha1, sha256=sha256, sha512=sha512)

    def copy(self) -> "TripleHashEngine":
        """現在の状態をコピー（中断・再開用）"""
        new = TripleHashEngine(**self._enabled)
        if new._md5 and self._md5:
            new._md5 = self._md5.copy()
        if new._sha1 and self._sha1:
            new._sha1 = self._sha1.copy()
        if new._sha256 and self._sha256:
            new._sha256 = self._sha256.copy()
        if new._sha512 and self._sha512:
            new._sha512 = self._sha512.copy()
        new._bytes_processed = self._bytes_processed
        return new


def verify_image_hash(
    image_path: str | Path,
    expected: dict[str, str],
    buffer_size: int = 1_048_576,
    progress_callback: Optional[Callable] = None,
    cancel_event: Optional[threading.Event] = None,
    *,
    md5: bool = True,
    sha1: bool = True,
    sha256: bool = True,
    sha512: bool = False,
) -> dict:
    """
    出力イメージファイルを再読取してハッシュを計算し、期待値と比較。
    """
    engine = TripleHashEngine(
        md5=md5, sha1=sha1, sha256=sha256, sha512=sha512
    )
    file_path = Path(image_path)
    file_size = file_path.stat().st_size

    logger.info(f"イメージ検証開始: {file_path} ({file_size} bytes)")

    with open(file_path, "rb") as f:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                computed = engine.hexdigests()
                return {
                    "computed": computed,
                    "cancelled": True,
                    "all_match": False,
                }
            data = f.read(buffer_size)
            if not data:
                break
            if cancel_event is not None and cancel_event.is_set():
                computed = engine.hexdigests()
                return {
                    "computed": computed,
                    "cancelled": True,
                    "all_match": False,
                }
            engine.update(data)

            if progress_callback:
                progress_callback(engine.bytes_processed, file_size)

    computed = engine.hexdigests()

    result: dict = {"computed": computed, "cancelled": False}
    checks = []
    if md5 and "md5" in computed:
        result["md5_match"] = computed["md5"] == expected.get("md5", "")
        checks.append(result["md5_match"])
    if sha1 and "sha1" in computed:
        result["sha1_match"] = computed["sha1"] == expected.get("sha1", "")
        checks.append(result["sha1_match"])
    if sha256 and "sha256" in computed:
        result["sha256_match"] = computed["sha256"] == expected.get("sha256", "")
        checks.append(result["sha256_match"])
    if sha512 and "sha512" in computed:
        result["sha512_match"] = computed["sha512"] == expected.get("sha512", "")
        checks.append(result["sha512_match"])

    result["all_match"] = bool(checks) and all(checks)

    if result["all_match"]:
        logger.info("イメージ検証: ✅ 全ハッシュ一致")
    else:
        logger.error("イメージ検証: ❌ ハッシュ不一致")
        for algo in ["md5", "sha1", "sha256", "sha512"]:
            k = f"{algo}_match"
            if k in result and not result[k]:
                logger.error(
                    f"  {algo}: expected={expected.get(algo, 'N/A')}, "
                    f"computed={computed.get(algo, 'N/A')}"
                )

    return result
