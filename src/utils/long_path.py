"""
MFEPS — Windows 長パス（MAX_PATH 超）対応
拡張パスプレフィックス \\\\?\\ および \\\\?\\UNC\\
"""
import os
import logging
from pathlib import Path

logger = logging.getLogger("mfeps.long_path")

# ewfacquire 等の互換性を考慮し、これ以下なら拡張プレフィクスを付けない
LONG_PATH_THRESHOLD = 240
_LONG_PATH_THRESHOLD = LONG_PATH_THRESHOLD
_WIN32_MAX_PATH = 32767
# レガシー MAX_PATH（拡張プレフィクス不要の上限）。CLI ツール互換用。
WIN32_CLASSIC_MAX_PATH = 260


def ensure_long_path(path: str | Path) -> str:
    """
    パスが長い場合に \\\\?\\ または \\\\?\\UNC\\ プレフィクスを付与する。
    既に拡張形式ならそのまま返す。短いパスは正規化した文字列を返す。
    """
    s = os.path.normpath(os.path.abspath(str(path)))
    if s.startswith("\\\\?\\"):
        return s
    if len(s) <= _LONG_PATH_THRESHOLD:
        return s
    if s.startswith("\\\\"):
        # UNC: \\server\share\...
        return "\\\\?\\UNC\\" + s[2:]
    return "\\\\?\\" + s


def validate_path_length(path: str, max_length: int = _WIN32_MAX_PATH) -> bool:
    """Win32 実効パス長の上限チェック（既定 32767）。"""
    return len(path) <= max_length


def maybe_extend_path(path: str | Path) -> Path:
    """閾値超のみ ensure_long_path を適用し、短いパスは Path のまま返す。"""
    p = Path(path)
    try:
        s = str(p.resolve())
    except OSError:
        s = str(p)
    if len(s) <= LONG_PATH_THRESHOLD:
        return p
    return Path(ensure_long_path(p))


def ensure_cli_path(path: str | Path) -> str:
    """
    外部プロセス（ewfacquire 等）向けパス文字列。
    260 文字以下では \\\\?\\ を付けず、超過時のみ ensure_long_path を適用する。
    """
    s = os.path.normpath(os.path.abspath(str(path)))
    if s.startswith("\\\\?\\"):
        return s
    if len(s) <= WIN32_CLASSIC_MAX_PATH:
        return s
    return ensure_long_path(s)


def shorten_component(name: str, max_len: int = 200) -> str:
    """ファイル名または最終ディレクトリ名を max_len 以内に切り詰め、拡張子は維持する。"""
    if len(name) <= max_len:
        return name
    p = Path(name)
    stem, suf = p.stem, p.suffix
    budget = max_len - len(suf)
    if budget < 1:
        return name[:max_len]
    return stem[:budget] + suf
