from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


class TestUsbWizardStepper:
    def test_wizard_page_loads(self, authenticated_page, app_url):
        """USB/HDD ページが描画される"""
        authenticated_page.goto(f"{app_url}/usb-hdd")
        authenticated_page.wait_for_timeout(2000)
        c = authenticated_page.content()
        assert "USB" in c or "HDD" in c

    def test_stepper_step1_visible(self, authenticated_page, app_url):
        """ステップ1（ドライブ選択）が表示される"""
        authenticated_page.goto(f"{app_url}/usb-hdd")
        authenticated_page.wait_for_timeout(2000)
        c = authenticated_page.content()
        assert "ドライブ" in c or "デバイス" in c

    def test_no_devices_message(self, authenticated_page, app_url):
        """デバイス検出フローに関する文言が表示される"""
        authenticated_page.goto(f"{app_url}/usb-hdd")
        authenticated_page.wait_for_timeout(3000)
        content = authenticated_page.content()
        assert "検出" in content or "デバイス" in content

    def test_optical_page_loads(self, authenticated_page, app_url):
        """光学メディアページが描画される"""
        authenticated_page.goto(f"{app_url}/optical")
        authenticated_page.wait_for_timeout(2000)
        c = authenticated_page.content()
        assert "CD" in c or "DVD" in c or "光学" in c
