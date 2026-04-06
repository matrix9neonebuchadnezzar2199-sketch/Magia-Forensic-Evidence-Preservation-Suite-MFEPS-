from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


class TestSettingsPage:
    def test_settings_loads(self, authenticated_page, app_url):
        """設定ページが描画される"""
        authenticated_page.goto(f"{app_url}/settings")
        authenticated_page.wait_for_timeout(2000)
        assert "設定" in authenticated_page.content()

    def test_font_size_slider_exists(self, authenticated_page, app_url):
        """フォントサイズスライダーが存在する"""
        authenticated_page.goto(f"{app_url}/settings")
        authenticated_page.wait_for_timeout(2000)
        assert "フォント" in authenticated_page.content()

    def test_theme_section_exists(self, authenticated_page, app_url):
        """テーマ設定セクションが存在する"""
        authenticated_page.goto(f"{app_url}/settings")
        authenticated_page.wait_for_timeout(2000)
        content = authenticated_page.content()
        assert "テーマ" in content or "theme" in content.lower()
