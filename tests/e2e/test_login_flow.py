from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


class TestLoginFlow:
    def test_login_page_renders(self, page, app_url):
        """ログインページに username/password 入力とボタンが描画される"""
        page.goto(f"{app_url}/login")
        assert page.locator("input").first.is_visible()
        assert page.locator("input[type='password']").is_visible()
        page.get_by_role("button", name="ログイン").wait_for(state="visible")

    def test_successful_login(self, page, app_url):
        """正しい認証情報でダッシュボードに遷移する"""
        page.goto(f"{app_url}/login")
        page.locator("input").first.fill("admin")
        page.locator("input[type='password']").fill("TestAdmin123!")
        page.get_by_role("button", name="ログイン").click()
        page.wait_for_url(f"{app_url}/", timeout=20000)
        assert "ダッシュボード" in page.content()

    def test_wrong_password_shows_error(self, page, app_url):
        """不正パスワードでエラー表示"""
        page.goto(f"{app_url}/login")
        page.locator("input").first.fill("admin")
        page.locator("input[type='password']").fill("WrongPass!")
        page.get_by_role("button", name="ログイン").click()
        page.wait_for_timeout(2000)
        assert (
            "正しくありません" in page.content()
            or page.locator(".q-notification").count() > 0
        )

    def test_unauthenticated_redirect(self, page, app_url):
        """未認証で / にアクセスすると /login にリダイレクトされる"""
        page.goto(f"{app_url}/")
        page.wait_for_timeout(3000)
        assert "/login" in page.url

    def test_logout_redirects_to_login(self, authenticated_page, app_url):
        """ログアウトボタンで /login にリダイレクトされる"""
        authenticated_page.get_by_role("button", name="ログアウト").click()
        authenticated_page.wait_for_timeout(3000)
        assert "/login" in authenticated_page.url
