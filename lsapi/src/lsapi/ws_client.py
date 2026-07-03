"""Async WebSocket client for LS Securities real-time market data.

This is a thin async facade over the synchronous :class:`~lsapi.realtime.LSRealtime`
engine (the proven, thread-based implementation). The realtime connection runs on
its own daemon thread; each incoming frame is bridged back onto the asyncio event
loop so async callbacks (``async def on_tick(msg): ...``) work transparently.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lsapi.auth import TokenManager
from lsapi.config import LSConfig
from lsapi.realtime import LSRealtime

_log = logging.getLogger(__name__)

Handler = Callable[[dict], Any]  # sync or async callable


class LSWebSocketClient:
    """Async real-time client.

    Usage::

        async with LSWebSocketClient(app_key, app_secret) as ws:
            await ws.subscribe("S3_", "005930", callback=on_tick)
            await asyncio.sleep(60)

    Handler signature (both supported)::

        def on_tick(msg: dict) -> None: ...          # sync
        async def on_tick(msg: dict) -> None: ...    # async

    The underlying engine auto-reconnects and replays active subscriptions.
    """

    def __init__(
        self,
        app_key: str | None = None,
        app_secret: str | None = None,
        *,
        config: LSConfig | None = None,
        token_manager: TokenManager | None = None,
        cache_dir: str | Path | None = None,
        reconnect_delay: float = 1.0,  # accepted for backwards compatibility
        **realtime_kwargs: Any,
    ) -> None:
        if config is None:
            overrides: dict[str, Any] = {"app_key": app_key, "app_secret": app_secret}
            if cache_dir is not None:
                overrides["cache_dir"] = str(Path(cache_dir).expanduser())
            config = LSConfig.from_env(**overrides)
        self._cfg = config
        self._auth = token_manager or TokenManager(config)
        self._realtime_kwargs = realtime_kwargs
        self._rt: LSRealtime | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._default_handler: Handler | None = None

    async def __aenter__(self) -> "LSWebSocketClient":
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._rt = LSRealtime(self._cfg, self._auth, **self._realtime_kwargs)
        await asyncio.to_thread(self._rt.connect)

    async def close(self) -> None:
        if self._rt is not None:
            await asyncio.to_thread(self._rt.stop)
            self._rt = None

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    async def subscribe(self, tr_cd: str, tr_key: str, callback: Handler) -> None:
        """Subscribe to real-time data.

        Args:
            tr_cd:    Real-time TR code (e.g. "S3_", "K3_", "JIF").
            tr_key:   Subscription key (e.g. stock code "005930"; "" for none).
            callback: Handler called on each incoming message (sync or async).
        """
        if self._rt is None:
            await self.connect()
        assert self._rt is not None
        shim = self._make_shim(callback)
        await asyncio.to_thread(self._rt.subscribe, tr_cd, tr_key, shim)

    async def unsubscribe(self, tr_cd: str, tr_key: str) -> None:
        """Unsubscribe from real-time data."""
        if self._rt is not None:
            await asyncio.to_thread(self._rt.unsubscribe, tr_cd, tr_key)

    def on_default(self, callback: Handler) -> None:
        """Set a fallback handler called when no tr_cd/tr_key handler matches."""
        self._default_handler = callback
        if self._rt is not None:
            self._rt.on_message(self._make_shim(callback))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _make_shim(self, callback: Handler) -> Callable[[dict], None]:
        """Wrap a user callback so it runs on the event loop from the ws thread."""
        loop = self._loop

        def _on_done(fut: "asyncio.Future[None]") -> None:
            if not fut.cancelled() and (exc := fut.exception()) is not None:
                _log.error("async realtime handler raised: %r", exc, exc_info=exc)

        def shim(msg: dict) -> None:
            _log.debug("shim: dispatching msg tr_cd=%r", (msg.get("header") or {}).get("tr_cd"))
            try:
                result = callback(msg)
            except Exception:  # noqa: BLE001
                _log.exception("realtime handler raised")
                return
            if asyncio.iscoroutine(result):
                if loop is None:  # pragma: no cover - connect() always sets it
                    _log.warning("async handler but no event loop captured; dropping")
                    return
                asyncio.run_coroutine_threadsafe(result, loop).add_done_callback(_on_done)

        return shim
