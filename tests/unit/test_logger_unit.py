"""logger ユーティリティの直接テスト"""
import src.utils.logger as logger_mod


def test_get_logger_name():
    lg = logger_mod.get_logger("unit_test")
    assert lg.name == "mfeps.unit_test"


def test_setup_logging_creates_files(tmp_path, monkeypatch):
    monkeypatch.setattr(logger_mod, "_initialized", False)
    logs = tmp_path / "logs"
    logger_mod.setup_logging(logs, "INFO")
    assert (logs / "app.log").exists()
    assert (logs / "imaging.log").exists()
    assert (logs / "audit.log").exists()
