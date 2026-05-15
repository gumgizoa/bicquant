"""LS Securities WebSocket client for real-time market data."""

import json
from collections.abc import AsyncIterator
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from lsapi.auth import TokenManager
from lsapi.exceptions import LSApiError

_WS_URL = "wss://openapi.ls-sec.co.kr:9443/websocket"


class LSWebSocketClient:
    """WebSocket client for LS Securities real-time data.

    Usage:
        async with LSWebSocketClient(app_key, app_secret) as ws:
            async for msg in ws.subscribe("S3_", {"shcode": "005930"}):
                print(msg)
    """

    def __init__(self, app_key: str, app_secret: str) -> None:
        self._tokens = TokenManager(app_key, app_secret)
        self._app_key = app_key
        self._conn: ClientConnection | None = None

    async def __aenter__(self) -> "LSWebSocketClient":
        token = await self._tokens.get()
        self._conn = await websockets.connect(_WS_URL)
        await self._login(token)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._conn:
            await self._conn.close()

    async def _login(self, token: str) -> None:
        msg = {
            "header": {
                "token": token,
                "tr_type": "1",
            },
            "body": {},
        }
        await self._conn.send(json.dumps(msg))  # type: ignore[union-attr]
        resp = json.loads(await self._conn.recv())  # type: ignore[union-attr]
        if resp.get("header", {}).get("rsp_cd") != "0000":
            raise LSApiError(f"WebSocket login failed: {resp}")

    async def subscribe(self, tr_cd: str, body: dict[str, Any]) -> AsyncIterator[dict]:
        """Subscribe to a real-time data feed and yield incoming messages."""
        if not self._conn:
            raise LSApiError("Not connected — use as async context manager")
        req = {
            "header": {"tr_type": "3", "tr_cd": tr_cd},
            "body": body,
        }
        await self._conn.send(json.dumps(req))
        async for raw in self._conn:
            yield json.loads(raw)
