"""テーマ CSS テスト"""


def test_light_css_contains_variables():
    from src.ui.theme.light_theme import LIGHT_CSS

    assert "--mfeps-bg" in LIGHT_CSS
    assert "--mfeps-surface" in LIGHT_CSS
    assert "mfeps-light" in LIGHT_CSS


def test_dark_css_exists():
    from src.ui.theme.modern_dark import CUSTOM_CSS

    assert isinstance(CUSTOM_CSS, str)
    assert len(CUSTOM_CSS) > 0


def test_light_css_has_card_style():
    from src.ui.theme.light_theme import LIGHT_CSS

    assert ".q-card" in LIGHT_CSS
