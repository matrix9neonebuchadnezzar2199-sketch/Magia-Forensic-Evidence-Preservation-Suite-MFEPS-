"""
不完全出力ファイルの検出（キャンセル・失敗時の通知用）。
ファイルは削除せず、列挙のみ行う。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def detect_incomplete_files(output_dir: str, patterns: list[str]) -> list[dict[str, Any]]:
    """
    output_dir 直下で patterns に一致するファイルを列挙する。

    patterns:
      - グロブを含む場合（* ? []）: Path.glob
      - それ以外: 直下の単一ファイル名として解決

    各要素: path（絶対パス文字列）, size_bytes, modified_at（UTC ISO8601）
    """
    root = Path(output_dir)
    if not root.is_dir():
        return []

    seen: set[str] = set()
    rows: list[dict[str, Any]] = []

    for pat in patterns:
        if any(c in pat for c in "*?[]"):
            for p in sorted(root.glob(pat), key=lambda x: str(x).lower()):
                if p.is_file():
                    _append_file_row(p, seen, rows)
        else:
            p = root / pat
            if p.is_file():
                _append_file_row(p, seen, rows)

    rows.sort(key=lambda r: r["path"].lower())
    return rows


def _append_file_row(path: Path, seen: set[str], rows: list[dict[str, Any]]) -> None:
    key = str(path.resolve())
    if key in seen:
        return
    seen.add(key)
    st = path.stat()
    modified = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
    rows.append(
        {
            "path": key,
            "size_bytes": st.st_size,
            "modified_at": modified,
        }
    )
