"""設定モジュールのテスト"""


class TestConfig:
    def test_default_values(self):
        from src.utils.config import MFEPSConfig

        cfg = MFEPSConfig()
        assert cfg.mfeps_port == 8580
        assert cfg.mfeps_buffer_size == 1_048_576
        assert cfg.mfeps_theme == "dark"
        assert cfg.bind_address == "127.0.0.1"
        assert cfg.session_timeout_hours == 8

    def test_output_dir_resolution(self, tmp_path):
        from src.utils.config import MFEPSConfig

        cfg = MFEPSConfig(mfeps_output_dir=str(tmp_path / "out"))
        assert "out" in str(cfg.output_dir)

    def test_db_path(self):
        from src.utils.config import MFEPSConfig

        cfg = MFEPSConfig()
        assert str(cfg.db_path).endswith("mfeps.db")
