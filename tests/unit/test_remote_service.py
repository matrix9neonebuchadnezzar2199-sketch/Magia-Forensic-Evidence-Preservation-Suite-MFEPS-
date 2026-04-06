from __future__ import annotations

import pytest

from src.services.remote_service import RemoteService


@pytest.fixture
def svc():
    return RemoteService()


class TestRemoteService:
    def test_register_agent(self, svc):
        assert svc.register_agent("A1", "host1", "10.0.0.1") is True

    def test_register_duplicate_rejected(self, svc):
        svc.register_agent("A1", "host1", "10.0.0.1")
        assert svc.register_agent("A1", "host1", "10.0.0.1") is False

    def test_unregister_agent(self, svc):
        svc.register_agent("A1", "host1", "10.0.0.1")
        assert svc.unregister_agent("A1") is True
        assert svc.get_agent("A1") is None

    def test_start_imaging_unknown_agent(self, svc):
        with pytest.raises(ValueError, match="not found"):
            svc.start_remote_imaging("UNKNOWN", r"\\.\PhysicalDrive1", "C1", "E1")

    def test_start_imaging_returns_job_id(self, svc):
        svc.register_agent("A1", "host1", "10.0.0.1")
        job_id = svc.start_remote_imaging("A1", r"\\.\PhysicalDrive1", "C1", "E1")
        assert len(job_id) == 36

    def test_heartbeat_updates_timestamp(self, svc):
        svc.register_agent("A1", "host1", "10.0.0.1")
        assert svc.heartbeat("A1") is True
        info = svc.get_agent("A1")
        assert info is not None
        assert info["status"] == "online"
