"""Singleton double-checked locking (Phase 2-3)"""
from concurrent.futures import ThreadPoolExecutor


class TestSingletonThreadSafety:
    def test_get_config_same_instance_parallel(self):
        import src.utils.config as cfgmod

        with cfgmod._config_lock:
            cfgmod._config = None

        def one():
            return cfgmod.get_config()

        with ThreadPoolExecutor(max_workers=8) as pool:
            refs = list(pool.map(lambda _: one(), range(50)))

        assert all(r is refs[0] for r in refs)

    def test_reload_config_new_instance(self):
        import src.utils.config as cfgmod

        with cfgmod._config_lock:
            cfgmod._config = None

        c1 = cfgmod.get_config()
        c2 = cfgmod.reload_config()
        assert c1 is not c2
        assert cfgmod.get_config() is c2
