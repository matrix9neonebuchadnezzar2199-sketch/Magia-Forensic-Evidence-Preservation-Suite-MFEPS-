"""RBAC ユニットテスト"""
from unittest.mock import patch

import pytest

from src.utils.rbac import check_action, check_page_access, has_permission


@pytest.fixture
def mock_role():
    """ユーザーロールをモックするヘルパー"""

    def _set(role):
        return patch("src.utils.rbac._get_user_role", return_value=role)

    return _set


def test_admin_has_all_permissions(mock_role):
    with mock_role("admin"):
        assert has_permission("admin")
        assert has_permission("examiner")
        assert has_permission("viewer")


def test_examiner_cannot_access_admin(mock_role):
    with mock_role("examiner"):
        assert not has_permission("admin")
        assert has_permission("examiner")
        assert has_permission("viewer")


def test_viewer_read_only(mock_role):
    with mock_role("viewer"):
        assert not has_permission("admin")
        assert not has_permission("examiner")
        assert has_permission("viewer")


def test_page_permissions_settings(mock_role):
    with mock_role("examiner"):
        assert not check_page_access("/settings")
    with mock_role("admin"):
        assert check_page_access("/settings")


def test_page_permissions_usb_hdd(mock_role):
    with mock_role("viewer"):
        assert not check_page_access("/usb-hdd")
    with mock_role("examiner"):
        assert check_page_access("/usb-hdd")


def test_action_imaging_start(mock_role):
    with mock_role("viewer"):
        assert not check_action("imaging.start")
    with mock_role("examiner"):
        assert check_action("imaging.start")


def test_action_user_management(mock_role):
    with mock_role("examiner"):
        assert not check_action("user.create")
    with mock_role("admin"):
        assert check_action("user.create")


def test_unknown_role_defaults_to_no_permission():
    with patch("src.utils.rbac._get_user_role", return_value="unknown"):
        assert not has_permission("viewer")
