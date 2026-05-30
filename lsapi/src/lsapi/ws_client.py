"""LS Securities WebSocket client for real-time market data."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from lsapi.auth import TokenManager
from lsapi.exceptions import LSApiError

_WS_URL = "wss://openapi.ls-sec.co.kr:9443/websocket"
_log = logging.getLogger(__name__)

Handler = Callable[[dict], Any]  # sync or async callable


class LSWebSocketClient:
    """WebSocket client for LS Securities real-time data.

    Usage:
        async with LSWebSocketClient(app_key, app_secret) as ws:
            await ws.subscribe("S3_", "005930", callback=on_tick)
            await asyncio.sleep(60)

    Handler signature:
        def on_tick(msg: dict) -> None: ...          # sync
        async def on_tick(msg: dict) -> None: ...    # async (both supported)

    Automatically reconnects after reconnect_delay seconds if the connection drops,
    replaying all active subscriptions.
    """

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        *,
        reconnect_delay: float = 1.0,
        cache_dir: str | Path | None = None,
    ) -> None:
        _cache = Path(cache_dir).expanduser() if cache_dir else None
        self._tokens = TokenManager(app_key, app_secret, cache_dir=_cache)
        self._conn: ClientConnection | None = None
        self._recv_task: asyncio.Task | None = None
        # {tr_cd: {tr_key: handler}}
        self._handlers: dict[str, dict[str, Handler]] = {}
        self._default_handler: Handler | None = None
        self._reconnect_delay = reconnect_delay
        self._stopping = False

    async def __aenter__(self) -> "LSWebSocketClient":
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        token = await self._tokens.get()
        self._conn = await websockets.connect(_WS_URL)
        await self._login(token)
        self._stopping = False
        self._recv_task = asyncio.create_task(self._recv_loop())

    async def close(self) -> None:
        self._stopping = True
        if self._recv_task:
            self._recv_task.cancel()
            self._recv_task = None
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    async def subscribe(self, tr_cd: str, tr_key: str, callback: Handler) -> None:
        """Subscribe to real-time data.

        Args:
            tr_cd:    Real-time TR code (e.g. "S3_", "K3_", "FC9").
            tr_key:   Subscription key (e.g. stock code "005930").
            callback: Handler called on each incoming message (sync or async).
        """
        if not self._conn:
            await self.connect()
        await self._send(
            {
                "header": {"tr_type": "3", "tr_cd": tr_cd},
                "body": {"tr_key": tr_key},
            }
        )
        self._handlers.setdefault(tr_cd, {})[tr_key] = callback

    async def unsubscribe(self, tr_cd: str, tr_key: str) -> None:
        """Unsubscribe from real-time data."""
        if self._conn:
            await self._send(
                {
                    "header": {"tr_type": "4", "tr_cd": tr_cd},
                    "body": {"tr_key": tr_key},
                }
            )
        self._handlers.get(tr_cd, {}).pop(tr_key, None)

    def on_default(self, callback: Handler) -> None:
        """Set a fallback handler called when no tr_cd/tr_key handler matches."""
        self._default_handler = callback

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _login(self, token: str) -> None:
        await self._send({"header": {"token": token, "tr_type": "1"}, "body": {}})
        resp = json.loads(await self._conn.recv())
        if resp.get("header", {}).get("rsp_cd") != "0000":
            raise LSApiError(f"WebSocket 로그인 실패: {resp}")

    async def _send(self, msg: dict) -> None:
        await self._conn.send(json.dumps(msg))

    async def _reconnect(self) -> None:
        """Reconnect and replay all active subscriptions."""
        with contextlib.suppress(Exception):
            await self._conn.close()
        token = await self._tokens.get()
        self._conn = await websockets.connect(_WS_URL)
        await self._login(token)
        for tr_cd, keys in list(self._handlers.items()):
            for tr_key in keys:
                await self._send(
                    {
                        "header": {"tr_type": "3", "tr_cd": tr_cd},
                        "body": {"tr_key": tr_key},
                    }
                )
        _log.info("LSWebSocketClient reconnected, replayed %d subscriptions", sum(len(v) for v in self._handlers.values()))

    async def _recv_loop(self) -> None:
        while not self._stopping:
            try:
                async for raw in self._conn:
                    msg = json.loads(raw)
                    header = msg.get("header", {})
                    tr_cd = header.get("tr_cd", "")
                    tr_key = header.get("tr_key", "") or msg.get("body", {}).get("tr_key", "")
                    handler = self._handlers.get(tr_cd, {}).get(tr_key) or self._default_handler
                    if handler is None:
                        continue
                    try:
                        result = handler(msg)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as exc:
                        _log.exception("handler error for %s/%s: %s", tr_cd, tr_key, exc)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if self._stopping:
                    break
                _log.warning("WebSocket disconnected (%s), reconnecting in %.1fs...", exc, self._reconnect_delay)
                await asyncio.sleep(self._reconnect_delay)
                with contextlib.suppress(Exception):
                    await self._reconnect()
