"""write_blocker のロジックテスト（レジストリ操作は mock）"""
from unittest.mock import patch, MagicMock


class TestWriteBlockerLogic:
    @patch("src.core.write_blocker.winreg")
    def test_is_global_write_blocked_true(self, mock_winreg):
        mock_key = MagicMock()
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = (1, 4)  # REG_DWORD=1
        mock_winreg.HKEY_LOCAL_MACHINE = 0x80000002
        mock_winreg.KEY_READ = 0x20019

        from src.core.write_blocker import is_global_write_blocked

        assert is_global_write_blocked() is True

    @patch("src.core.write_blocker.winreg")
    def test_is_global_write_blocked_false_no_key(self, mock_winreg):
        mock_winreg.OpenKey.side_effect = FileNotFoundError
        mock_winreg.HKEY_LOCAL_MACHINE = 0x80000002
        mock_winreg.KEY_READ = 0x20019

        from src.core.write_blocker import is_global_write_blocked

        assert is_global_write_blocked() is False

    @patch("src.core.write_blocker.winreg")
    def test_enable_creates_key_if_missing(self, mock_winreg):
        mock_winreg.OpenKey.side_effect = FileNotFoundError
        mock_key = MagicMock()
        mock_winreg.CreateKey.return_value = mock_key
        mock_winreg.HKEY_LOCAL_MACHINE = 0x80000002
        mock_winreg.KEY_SET_VALUE = 0x2
        mock_winreg.REG_DWORD = 4

        from src.core.write_blocker import enable_global_write_block

        result = enable_global_write_block()
        assert result is True
        mock_winreg.SetValueEx.assert_called_once()

    def test_get_protection_badge_hw(self):
        from src.core.write_blocker import get_protection_badge

        text, color, icon = get_protection_badge(
            {
                "hardware_blocked": True,
                "registry_blocked": False,
                "is_protected": True,
            }
        )
        assert color == "positive"
        assert "HW" in text

    def test_get_protection_badge_sw(self):
        from src.core.write_blocker import get_protection_badge

        text, color, icon = get_protection_badge(
            {
                "hardware_blocked": False,
                "registry_blocked": True,
                "is_protected": True,
            }
        )
        assert color == "warning"
        assert "SW" in text

    def test_get_protection_badge_none(self):
        from src.core.write_blocker import get_protection_badge

        text, color, icon = get_protection_badge(
            {
                "hardware_blocked": False,
                "registry_blocked": False,
                "is_protected": False,
            }
        )
        assert color == "negative"
