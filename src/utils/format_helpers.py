"""
MFEPS v2.1.0 — フォーマットヘルパー
バイト数の人間可読変換など汎用フォーマット関数
"""


def format_capacity(bytes_val: int) -> str:
    """バイト数を人間可読形式に変換

    Args:
        bytes_val: 変換するバイト数

    Returns:
        "1.23 GB" のような文字列。0 以下の場合は "不明"
    """
    if bytes_val <= 0:
        return "不明"
    units = [("TB", 1024**4), ("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)]
    for unit, divisor in units:
        if bytes_val >= divisor:
            return f"{bytes_val / divisor:.2f} {unit}"
    return f"{bytes_val} B"
