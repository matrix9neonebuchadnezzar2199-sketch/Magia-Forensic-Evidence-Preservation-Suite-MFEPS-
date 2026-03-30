"""
パスコンポーネントのサニタイズ（パストラバーサル・禁止文字の除去）
"""
import re

_MAX_COMPONENT_LEN = 100


def sanitize_path_component(name: str) -> str:
    """単一のディレクトリ名として安全な文字列に制限する。"""
    if not name or not isinstance(name, str):
        return "unnamed"
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)
    sanitized = sanitized.strip(". ")
    if not sanitized:
        sanitized = "unnamed"
    if ".." in sanitized:
        sanitized = sanitized.replace("..", "__")
    return sanitized[:_MAX_COMPONENT_LEN]
