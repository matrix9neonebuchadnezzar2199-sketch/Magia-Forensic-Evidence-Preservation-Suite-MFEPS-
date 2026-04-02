"""get_auth_service のスレッドセーフ初期化（Phase 5-5）"""
from concurrent.futures import ThreadPoolExecutor

import src.services.auth_service as authmod


class TestAuthServiceThreadSafety:
    def test_get_auth_service_returns_same_instance(self):
        with authmod._auth_service_lock:
            authmod._auth_service = None

        def one():
            return authmod.get_auth_service()

        with ThreadPoolExecutor(max_workers=10) as pool:
            refs = list(pool.map(lambda _: one(), range(30)))
        assert all(r is refs[0] for r in refs)

    def test_get_auth_service_concurrent_after_reset(self):
        with authmod._auth_service_lock:
            authmod._auth_service = None
        first = authmod.get_auth_service()

        with authmod._auth_service_lock:
            authmod._auth_service = None

        def one():
            return authmod.get_auth_service()

        with ThreadPoolExecutor(max_workers=10) as pool:
            refs = list(pool.map(lambda _: one(), range(30)))
        assert all(r is refs[0] for r in refs)
        assert refs[0] is not first
