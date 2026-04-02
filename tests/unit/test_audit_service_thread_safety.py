"""get_audit_service のスレッドセーフ初期化（Phase 4-3）"""
from concurrent.futures import ThreadPoolExecutor

import src.services.audit_service as audmod


class TestAuditServiceThreadSafety:
    def test_parallel_calls_same_instance(self):
        with audmod._audit_service_lock:
            audmod._audit_service = None

        def one():
            return audmod.get_audit_service()

        with ThreadPoolExecutor(max_workers=10) as pool:
            refs = list(pool.map(lambda _: one(), range(30)))
        assert all(r is refs[0] for r in refs)

    def test_after_reset_all_threads_see_one_new_instance(self):
        with audmod._audit_service_lock:
            audmod._audit_service = None
        first = audmod.get_audit_service()

        with audmod._audit_service_lock:
            audmod._audit_service = None

        def one():
            return audmod.get_audit_service()

        with ThreadPoolExecutor(max_workers=10) as pool:
            refs = list(pool.map(lambda _: one(), range(30)))
        assert all(r is refs[0] for r in refs)
        assert refs[0] is not first
