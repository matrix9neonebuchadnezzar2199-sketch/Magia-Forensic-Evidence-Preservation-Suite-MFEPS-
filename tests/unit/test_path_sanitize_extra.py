"""path_sanitize 境界"""
from src.utils.path_sanitize import sanitize_path_component


def test_non_string_returns_unnamed():
    assert sanitize_path_component(None) == "unnamed"  # type: ignore[arg-type]
    assert sanitize_path_component(1) == "unnamed"  # type: ignore[arg-type]
