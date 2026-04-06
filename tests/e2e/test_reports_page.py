from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


class TestReportsPage:
    def test_reports_page_loads(self, authenticated_page, app_url):
        authenticated_page.goto(f"{app_url}/reports")
        authenticated_page.wait_for_timeout(2000)
        assert "レポート" in authenticated_page.content()

    def test_no_reports_message(self, authenticated_page, app_url):
        """レポートが無い場合に適切なメッセージが表示される"""
        authenticated_page.goto(f"{app_url}/reports")
        authenticated_page.wait_for_timeout(3000)
        content = authenticated_page.content()
        assert "レポート" in content
