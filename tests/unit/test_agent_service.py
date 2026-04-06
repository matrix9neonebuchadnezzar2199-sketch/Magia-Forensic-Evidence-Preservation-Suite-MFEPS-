from __future__ import annotations

import pytest

from src.agent.agent_service import AgentService
from src.core.remote_protocol import JsonRpcRequest, JsonRpcResponse, RemoteProtocol


@pytest.fixture
def agent():
    return AgentService(server_url="ws://localhost:9999", agent_id="T1", secret="sec")


class TestAgentService:
    @pytest.mark.asyncio
    async def test_handle_device_list(self, agent):
        req = JsonRpcRequest(method="device.list", params={}, id="1")
        raw = RemoteProtocol.encode_request(req)
        resp_raw = await agent.handle_message(raw)
        assert resp_raw is not None
        resp = RemoteProtocol.decode(resp_raw)
        assert isinstance(resp, JsonRpcResponse)
        assert resp.result is not None
        assert "devices" in resp.result

    @pytest.mark.asyncio
    async def test_handle_unknown_method(self, agent):
        req = JsonRpcRequest(method="evil.hack", params={}, id="2")
        raw = RemoteProtocol.encode_request(req)
        resp_raw = await agent.handle_message(raw)
        assert resp_raw is not None
        resp = RemoteProtocol.decode(resp_raw)
        assert resp.error is not None

    @pytest.mark.asyncio
    async def test_handle_imaging_start(self, agent):
        req = JsonRpcRequest(
            method="imaging.start",
            params={"job_id": "j1", "device_path": r"\\.\PhysicalDrive1"},
            id="3",
        )
        resp_raw = await agent.handle_message(RemoteProtocol.encode_request(req))
        assert resp_raw is not None
        resp = RemoteProtocol.decode(resp_raw)
        assert resp.result is not None
        assert resp.result["accepted"] is True

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self, agent):
        resp_raw = await agent.handle_message("{invalid")
        assert resp_raw is not None
        resp = RemoteProtocol.decode(resp_raw)
        assert resp.error is not None

    @pytest.mark.asyncio
    async def test_connect_sets_connected(self, agent):
        sent: list[str] = []

        async def mock_send(x: str) -> None:
            sent.append(x)

        await agent.connect(send_func=mock_send)
        assert agent.is_connected
        assert len(sent) >= 1
