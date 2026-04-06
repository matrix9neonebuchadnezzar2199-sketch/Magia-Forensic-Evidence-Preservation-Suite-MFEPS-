from __future__ import annotations

import pytest

from src.core.remote_protocol import (
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    RemoteProtocol,
)


class TestRemoteProtocol:
    def test_encode_request(self):
        req = JsonRpcRequest(method="agent.register", params={"agent_id": "A1"})
        raw = RemoteProtocol.encode_request(req)
        assert "agent.register" in raw

    def test_decode_request(self):
        raw = '{"jsonrpc":"2.0","method":"device.list","params":{},"id":"abc"}'
        msg = RemoteProtocol.decode(raw)
        assert isinstance(msg, JsonRpcRequest)
        assert msg.method == "device.list"

    def test_decode_response(self):
        raw = '{"jsonrpc":"2.0","id":"abc","result":{"ok":true}}'
        msg = RemoteProtocol.decode(raw)
        assert isinstance(msg, JsonRpcResponse)
        assert msg.result is not None
        assert msg.result.get("ok") is True

    def test_decode_invalid_json(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            RemoteProtocol.decode("{broken")

    def test_decode_not_jsonrpc(self):
        with pytest.raises(ValueError, match="JSON-RPC"):
            RemoteProtocol.decode('{"foo": "bar"}')

    def test_validate_method_known(self):
        assert RemoteProtocol.validate_method("imaging.start") is True

    def test_validate_method_unknown(self):
        assert RemoteProtocol.validate_method("evil.method") is False

    def test_token_validation(self):
        token = RemoteProtocol.create_token("agent1", "secret")
        assert RemoteProtocol.validate_token(token, "agent1", "secret")
        assert not RemoteProtocol.validate_token(token, "agent1", "wrong")

    def test_decode_request_list_params(self):
        raw = '{"jsonrpc":"2.0","method":"device.list","params":[1,2],"id":"z"}'
        msg = RemoteProtocol.decode(raw)
        assert isinstance(msg, JsonRpcRequest)
        assert msg.params["_args"] == [1, 2]

    def test_decode_response_with_error_object(self):
        raw = (
            '{"jsonrpc":"2.0","id":"1","error":{"code":-32601,"message":"nope","data":{"x":1}}}'
        )
        msg = RemoteProtocol.decode(raw)
        assert isinstance(msg, JsonRpcResponse)
        assert msg.error is not None
        assert msg.error.code == -32601
        assert msg.error.data == {"x": 1}

    def test_encode_response_with_error(self):
        resp = JsonRpcResponse(
            id="a",
            error=JsonRpcError(code=1, message="m", data={"k": "v"}),
        )
        s = RemoteProtocol.encode_response(resp)
        assert "error" in s
        assert "data" in s
