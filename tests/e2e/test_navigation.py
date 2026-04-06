from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

SIDEBAR_PAGES = [
    ("/", "ダッシュボード"),
    ("/usb-hdd", "USB"),
    ("/optical", "CD"),
    ("/cases", "ケース"),
    ("/reports", "レポート"),
    ("/audit", "監査"),
    ("/settings", "設定"),
]


class TestNavigation:
    @pytest.mark.parametrize("path,keyword", SIDEBAR_PAGES)
    def test_page_loads(self, authenticated_page, app_url, path, keyword):
        """各ページに遷移し、主要キーワードが含まれることを確認"""
        authenticated_page.goto(f"{app_url}{path}")
        authenticated_page.wait_for_timeout(2000)
        content = authenticated_page.content()
        assert keyword in content, f"'{keyword}' not found on {path}"
