"""path_sanitize のユニットテスト"""

from src.utils.path_sanitize import sanitize_path_component


def test_sanitizes_traversal_and_forbidden_chars():
    assert ".." not in sanitize_path_component("a..b..c")
    assert "/" not in sanitize_path_component("x/y")
    assert sanitize_path_component("  ") == "unnamed"


def test_preserves_safe_names():
    assert sanitize_path_component("CASE-001") == "CASE-001"
