"""logger ユーティリティの直接テスト（setup はグローバル状態に触れるため最小限）"""
import src.utils.logger as logger_mod


def test_get_logger_name():
    lg = logger_mod.get_logger("unit_test")
    assert lg.name == "mfeps.unit_test"
