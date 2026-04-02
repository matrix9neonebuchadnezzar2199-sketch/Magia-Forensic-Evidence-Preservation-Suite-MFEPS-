"""config.py の追加カバレッジ"""

from src.utils.config import get_config, reload_config


def test_config_singleton():
    c1 = get_config()
    c2 = get_config()
    assert c1 is c2


def test_config_directories():
    c = get_config()
    assert c.logs_dir is not None
    assert c.reports_dir is not None
    assert c.db_path is not None


def test_config_e01_defaults():
    c = get_config()
    assert c.e01_compression_method == "deflate"
    assert c.e01_compression_level == "fast"
    assert c.e01_ewf_format == "encase6"


def test_config_ewfacquire_available():
    c = get_config()
    assert isinstance(c.ewfacquire_available, bool)


def test_reload_config():
    reload_config()
    c = get_config()
    assert c is not None
