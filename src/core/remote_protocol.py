"""
MFEPS — リモートイメージング JSON-RPC 2.0 プロトコル
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

logger = logging.getLogger("mfeps.remote_protocol")

# ─── JSON-RPC 2.0 メッセージ ───


@dataclass
class JsonRpcRequest:
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    jsonrpc: str = "2.0"


@dataclass
class JsonRpcError:
    code: int
    message: str
    data: Optional[dict[str, Any]] = None


@dataclass
class JsonRpcResponse:
    id: str
    result: Optional[dict[str, Any]] = None
    error: Optional[JsonRpcError] = None
    jsonrpc: str = "2.0"


# ─── JSON-RPC 標準エラー（一部） ───
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
AUTH_FAILED = -32000
AGENT_NOT_FOUND = -32001

# ─── 利用可能メソッド ───
KNOWN_METHODS = frozenset({
    "agent.register",
    "agent.heartbeat",
    "agent.unregister",
    "device.list",
    "imaging.start",
    "imaging.progress",
    "imaging.cancel",
    "imaging.complete",
})


class RemoteProtocol:
    """JSON-RPC 2.0 のシリアライズ / デシリアライズ / 認証"""

    @staticmethod
    def encode_request(req: JsonRpcRequest) -> str:
        return json.dumps(asdict(req), ensure_ascii=False)

    @staticmethod
    def encode_response(resp: JsonRpcResponse) -> str:
        d: dict[str, Any] = {"jsonrpc": resp.jsonrpc, "id": resp.id}
        if resp.error is not None:
            err: dict[str, Any] = {
                "code": resp.error.code,
                "message": resp.error.message,
            }
            if resp.error.data is not None:
                err["data"] = resp.error.data
            d["error"] = err
        else:
            d["result"] = resp.result
        return json.dumps(d, ensure_ascii=False)

    @staticmethod
    def decode(raw: str) -> JsonRpcRequest | JsonRpcResponse:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e
        if not isinstance(obj, dict) or obj.get("jsonrpc") != "2.0":
            raise ValueError("Not a valid JSON-RPC 2.0 message")
        if "method" in obj:
            rp = obj.get("params")
            if isinstance(rp, list):
                params: dict[str, Any] = {"_args": rp}
            elif isinstance(rp, dict):
                params = rp
            else:
                params = {}
            return JsonRpcRequest(
                method=obj["method"],
                params=params,
                id=str(obj.get("id", "")),
                jsonrpc="2.0",
            )
        err_obj = obj.get("error")
        err: Optional[JsonRpcError] = None
        if isinstance(err_obj, dict):
            err = JsonRpcError(
                code=int(err_obj["code"]),
                message=str(err_obj.get("message", "")),
                data=err_obj.get("data") if "data" in err_obj else None,
            )
        return JsonRpcResponse(
            id=str(obj.get("id", "")),
            result=obj.get("result") if "result" in obj else None,
            error=err,
            jsonrpc="2.0",
        )

    @staticmethod
    def validate_method(method: str) -> bool:
        return method in KNOWN_METHODS

    @staticmethod
    def create_token(agent_id: str, secret: str) -> str:
        return hmac.new(
            secret.encode(), agent_id.encode(), hashlib.sha256
        ).hexdigest()

    @staticmethod
    def validate_token(token: str, agent_id: str, secret: str) -> bool:
        expected = RemoteProtocol.create_token(agent_id, secret)
        return hmac.compare_digest(token, expected)

    @staticmethod
    def create_error_response(req_id: str, code: int, message: str) -> JsonRpcResponse:
        return JsonRpcResponse(
            id=req_id,
            error=JsonRpcError(code=code, message=message),
        )
