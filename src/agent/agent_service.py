"""
MFEPS — リモートイメージングエージェント
サーバーからの JSON-RPC 指示を受信し、ローカルでイメージングを実行する。
"""
from __future__ import annotations

import asyncio
import logging
import platform
from typing import Any, Callable, Coroutine, Optional

from src.core.remote_protocol import (
    INTERNAL_ERROR,
    JsonRpcRequest,
    JsonRpcResponse,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    RemoteProtocol,
)

logger = logging.getLogger("mfeps.agent")


class AgentService:
    def __init__(self, server_url: str, agent_id: str, secret: str) -> None:
        self.server_url = server_url
        self.agent_id = agent_id
        self.secret = secret
        self._token = RemoteProtocol.create_token(agent_id, secret)
        self._connected = False
        self._send_func: Optional[Callable[[str], Coroutine[Any, Any, None]]] = None
        self._jobs: dict[str, asyncio.Task] = {}

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(
        self, send_func: Callable[[str], Coroutine[Any, Any, None]]
    ) -> None:
        """WebSocket 送信関数を注入して接続完了とする。"""
        self._send_func = send_func
        self._connected = True
        req = JsonRpcRequest(
            method="agent.register",
            params={
                "agent_id": self.agent_id,
                "hostname": platform.node(),
                "ip": "0.0.0.0",
                "token": self._token,
            },
        )
        await self._send(RemoteProtocol.encode_request(req))
        logger.info("Agent connected to %s", self.server_url)

    async def disconnect(self) -> None:
        self._connected = False
        for task in self._jobs.values():
            task.cancel()
        self._jobs.clear()
        logger.info("Agent disconnected")

    async def handle_message(self, raw: str) -> Optional[str]:
        """サーバーからの JSON-RPC メッセージを処理し、レスポンスを返す。"""
        try:
            msg = RemoteProtocol.decode(raw)
        except ValueError as e:
            return RemoteProtocol.encode_response(
                RemoteProtocol.create_error_response("", PARSE_ERROR, str(e))
            )

        if isinstance(msg, JsonRpcResponse):
            logger.debug("Received response: id=%s", msg.id)
            return None

        if not RemoteProtocol.validate_method(msg.method):
            return RemoteProtocol.encode_response(
                RemoteProtocol.create_error_response(
                    msg.id, METHOD_NOT_FOUND, f"Unknown: {msg.method}"
                )
            )

        handler = {
            "device.list": self._on_device_list,
            "imaging.start": self._on_imaging_start,
            "imaging.cancel": self._on_imaging_cancel,
        }.get(msg.method)

        if handler is None:
            return RemoteProtocol.encode_response(
                RemoteProtocol.create_error_response(
                    msg.id, METHOD_NOT_FOUND, msg.method
                )
            )

        try:
            result = await handler(msg.params)
            return RemoteProtocol.encode_response(JsonRpcResponse(id=msg.id, result=result))
        except Exception as e:
            logger.error("Handler error: %s", e, exc_info=True)
            return RemoteProtocol.encode_response(
                RemoteProtocol.create_error_response(msg.id, INTERNAL_ERROR, str(e))
            )

    async def _on_device_list(self, params: dict) -> dict:
        del params
        try:
            from src.core.device_detector import detect_block_devices

            devices = detect_block_devices()
            return {
                "devices": [
                    {
                        "path": d.device_path,
                        "model": d.model,
                        "serial": d.serial,
                        "capacity": d.capacity_bytes,
                    }
                    for d in devices
                ]
            }
        except Exception as e:
            return {"devices": [], "error": str(e)}

    async def _on_imaging_start(self, params: dict) -> dict:
        job_id = params.get("job_id", "")
        device_path = params.get("device_path", "")
        if not job_id or not device_path:
            raise ValueError("job_id and device_path required")
        logger.info("Remote imaging start: job=%s device=%s", job_id, device_path)
        return {"job_id": job_id, "accepted": True}

    async def _on_imaging_cancel(self, params: dict) -> dict:
        job_id = params.get("job_id", "")
        task = self._jobs.get(job_id)
        if task:
            task.cancel()
        return {"job_id": job_id, "cancelled": True}

    async def _send(self, data: str) -> None:
        if self._send_func:
            await self._send_func(data)

    async def heartbeat_loop(self, interval: int = 30) -> None:
        while self._connected:
            req = JsonRpcRequest(
                method="agent.heartbeat",
                params={"agent_id": self.agent_id, "token": self._token},
            )
            await self._send(RemoteProtocol.encode_request(req))
            await asyncio.sleep(interval)
