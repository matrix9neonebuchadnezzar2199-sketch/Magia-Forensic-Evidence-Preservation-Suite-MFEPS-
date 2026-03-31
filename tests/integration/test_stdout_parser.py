"""
E01 stdout パーサー検証（実機統合テストの必須ゲート）

実環境で ewfacquire を実行し、stdout をファイルに保存したあと本スクリプトで
constants.py の正規表現と照合する。

Usage (repo root):
  python tests/integration/test_stdout_parser.py [path/to/stdout.txt]

引数なしの場合、同ディレクトリの ewfacquire_stdout_sample.txt を使用する。

Note: ハッシュ行は E01_HASH_PATTERN（アルゴリズム名可変）で一括マッチする。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.utils.constants import (  # noqa: E402
    E01_BYTES_PATTERN,
    E01_HASH_PATTERN,
    E01_PROGRESS_PATTERN,
    EWFVERIFY_COMPUTED_HASH_PATTERN,
    EWFVERIFY_STORED_HASH_PATTERN,
    EWFVERIFY_SUCCESS_PATTERN,
)

# ドキュメント例に出る ewfacquire 完了行（実装では未使用だがゲートで確認可能）
E01_ACQUIRE_SUCCESS_PATTERN = r"ewfacquire:\s+SUCCESS"


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def verify_ewfacquire_stdout(stdout: str) -> list[str]:
    """マッチしなかったパターン名のリストを返す（空なら合格）"""
    failed: list[str] = []
    if not re.search(E01_PROGRESS_PATTERN, stdout):
        failed.append("E01_PROGRESS_PATTERN")
    if not re.search(E01_BYTES_PATTERN, stdout):
        failed.append("E01_BYTES_PATTERN")
    if not re.search(E01_HASH_PATTERN, stdout):
        failed.append("E01_HASH_PATTERN")
    # 任意: 一部ビルドでは最後に SUCCESS 行が出る
    if "ewfacquire" in stdout.lower() and "success" in stdout.lower():
        if not re.search(E01_ACQUIRE_SUCCESS_PATTERN, stdout, re.IGNORECASE):
            # 厳密に必須にしない — 警告のみ
            pass
    return failed


def verify_ewfverify_stdout(stdout: str) -> list[str]:
    failed: list[str] = []
    if not re.search(EWFVERIFY_SUCCESS_PATTERN, stdout):
        failed.append("EWFVERIFY_SUCCESS_PATTERN")
    if not re.search(EWFVERIFY_STORED_HASH_PATTERN, stdout):
        failed.append("EWFVERIFY_STORED_HASH_PATTERN")
    if not re.search(EWFVERIFY_COMPUTED_HASH_PATTERN, stdout):
        failed.append("EWFVERIFY_COMPUTED_HASH_PATTERN")
    return failed


def main() -> int:
    here = Path(__file__).resolve().parent
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "ewfacquire_stdout_sample.txt"
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 2

    text = _read_text(path)
    failed = verify_ewfacquire_stdout(text)

    if failed:
        print("FAILED - patterns with no match:", ", ".join(failed))
        print("--- stdout (head 800) ---")
        print(text[:800])
        print("--- stdout (tail 800) ---")
        print(text[-800:])
        return 1

    print("OK - E01_PROGRESS_PATTERN, E01_BYTES_PATTERN, E01_HASH_PATTERN matched.")
    if re.search(E01_ACQUIRE_SUCCESS_PATTERN, text, re.IGNORECASE):
        print("     (optional) ewfacquire: SUCCESS line present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
