"""Realtime (WebSocket) client — synchronous engine.

LS Securities exposes a single WebSocket endpoint at
``wss://openapi.ls-sec.co.kr:9443/websocket``. Each subscription is a JSON
message::

    {"header": {"token": "<access>", "tr_type": "3"}, "body": {"tr_cd": "S3_", "tr_key": "005930"}}

``tr_type`` values: ``3`` = 실시간 시세 등록, ``4`` = 실시간 시세 해제.

Messages from the server are delivered to user callbacks keyed by ``tr_cd``;
unknown TR codes go to the default callback (if any). The connection runs on a
daemon thread and reconnects automatically, replaying active subscriptions.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable, Optional

from lsapi.auth import TokenManager
from lsapi.config import LSConfig
from lsapi.exceptions import LSApiError

try:
    import websocket  # websocket-client
except ImportError:  # pragma: no cover
    websocket = None  # type: ignore[assignment]


log = logging.getLogger("lsapi.realtime")

Handler = Callable[[dict], None]


class LSRealtime:
    """Thread-based WebSocket client.

    Basic flow::

        rt = client.realtime()
        rt.subscribe("S3_", "005930", on_trade)
        rt.run_forever()                    # blocks until stop()

    The connection is opened lazily on the first ``subscribe`` call (or
    ``connect()``). Reconnects on unexpected disconnects are enabled by default.
    """

    TR_REGISTER = "3"
    TR_UNREGISTER = "4"

    def __init__(
        self,
        config: LSConfig,
        token_manager: TokenManager,
        *,
        auto_reconnect: bool = True,
        ping_interval: float = 20.0,
    ) -> None:
        if websocket is None:
            raise LSApiError("the 'websocket-client' package is required for realtime support.\nInstall it with:  pip install websocket-client")
        self._cfg = config
        self._auth = token_manager
        self._auto_reconnect = auto_reconnect
        self._ping_interval = ping_interval

        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._connected = threading.Event()
        self._stopping = threading.Event()
        self._lock = threading.Lock()

        # { tr_cd: { tr_key: handler } }
        self._handlers: dict[str, dict[str, Handler]] = {}
        self._default_handler: Optional[Handler] = None
        # Pending subscriptions to replay on (re)connect
        self._subs: list[tuple[str, str]] = []

        # Rapid-disconnect tracking for token-rejection detection
        self._last_open_time: float = 0.0
        self._rapid_close_count: int = 0

    # --------------------------------------------------------- public API

    def on_message(self, handler: Handler) -> None:
        """Register a default handler for messages with no per-TR callback."""
        self._default_handler = handler

    def subscribe(self, tr_cd: str, tr_key: str, handler: Handler | None = None) -> None:
        with self._lock:
            if (tr_cd, tr_key) not in self._subs:
                self._subs.append((tr_cd, tr_key))
            if handler:
                self._handlers.setdefault(tr_cd, {})[tr_key] = handler
        self._ensure_connected()
        self._send_register(tr_cd, tr_key)

    def unsubscribe(self, tr_cd: str, tr_key: str) -> None:
        with self._lock:
            try:
                self._subs.remove((tr_cd, tr_key))
            except ValueError:
                pass
            handlers = self._handlers.get(tr_cd)
            if handlers:
                handlers.pop(tr_key, None)
        if self._ws is not None:
            self._send(
                {
                    "header": {"token": self._auth.token, "tr_type": self.TR_UNREGISTER},
                    "body": {"tr_cd": tr_cd, "tr_key": tr_key},
                }
            )

    def subscribe_many(self, topics: list[tuple[str, str]], handler: Handler) -> None:
        """Subscribe to a batch of (tr_cd, tr_key) pairs with one handler."""
        for tr_cd, tr_key in topics:
            self.subscribe(tr_cd, tr_key, handler)

    def connect(self) -> None:
        self._ensure_connected()

    def run_forever(self) -> None:
        """Block the caller until :meth:`stop` is called."""
        self._ensure_connected()
        try:
            while not self._stopping.is_set():
                time.sleep(0.25)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        self._stopping.set()
        ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def topics(category: str | None = None):
        """List realtime TR codes (delegates to the generated topic table)."""
        from lsapi.realtime_topics import REALTIME_TOPICS, list_topics

        if category is None:
            return list_topics()
        return dict(REALTIME_TOPICS.get(category, {}))

    # -------------------------------------------------------- internals

    def _ensure_connected(self) -> None:
        if self._connected.is_set():
            return
        with self._lock:
            if self._connected.is_set():
                return
            self._stopping.clear()
            self._ws = self._new_app()
            self._ws_thread = threading.Thread(target=self._run_ws, name="lsapi-ws", daemon=True)
            self._ws_thread.start()
        if not self._connected.wait(timeout=self._cfg.timeout * 2):
            raise LSApiError("websocket did not connect in time")

    def _new_app(self):
        return websocket.WebSocketApp(
            self._cfg.ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

    # Connections that last shorter than this are treated as token-rejection "Bye"s.
    _RAPID_CLOSE_THRESHOLD = 3.0

    def _run_ws(self) -> None:
        assert self._ws is not None
        while not self._stopping.is_set():
            try:
                self._ws.run_forever(ping_interval=self._ping_interval)
            except Exception as e:  # noqa: BLE001
                log.warning("ws run error: %s", e)
            if not self._auto_reconnect or self._stopping.is_set():
                break
            self._connected.clear()

            elapsed = time.time() - self._last_open_time if self._last_open_time else float("inf")
            if elapsed < self._RAPID_CLOSE_THRESHOLD:
                self._rapid_close_count += 1
                if self._rapid_close_count == 1:
                    # First rapid disconnect: token was likely rejected — invalidate it
                    # so the next attempt fetches a fresh one from the API.
                    log.warning("ws: rapid disconnect (%.2fs) — invalidating token and retrying", elapsed)
                    self._auth.invalidate()
                delay = min(1.0 * (2 ** min(self._rapid_close_count - 1, 6)), 60.0)
                log.debug("ws: rapid_close_count=%d, reconnecting in %.0fs", self._rapid_close_count, delay)
            else:
                self._rapid_close_count = 0
                delay = 1.0

            time.sleep(delay)
            self._ws = self._new_app()  # rebuild so run_forever can be called again
        self._connected.clear()

    def _on_open(self, ws) -> None:  # noqa: ANN001
        log.info("ws open: %s", self._cfg.ws_url)
        self._last_open_time = time.time()
        self._rapid_close_count = 0
        self._connected.set()
        for tr_cd, tr_key in list(self._subs):  # replay subscriptions on reconnect
            self._send_register(tr_cd, tr_key)

    def _on_message(self, ws, raw: str) -> None:  # noqa: ANN001
        try:
            msg = json.loads(raw)
        except Exception:  # noqa: BLE001
            log.warning("bad ws frame: %s", raw[:200])
            return
        header = msg.get("header") or {}
        body = msg.get("body") or {}
        tr_cd = header.get("tr_cd") or ""
        tr_key = header.get("tr_key") or body.get("tr_key") or ""
        log.debug("ws rx: tr_cd=%r tr_key=%r rsp_cd=%r", tr_cd, tr_key, header.get("rsp_cd"))
        handler = None
        handlers = self._handlers.get(tr_cd)
        if handlers:
            handler = handlers.get(tr_key) or handlers.get("")
        if handler is None:
            handler = self._default_handler
        if handler is None:
            log.debug("ws rx: no handler for tr_cd=%r tr_key=%r (subscribed: %s)", tr_cd, tr_key, list(self._handlers))
        if handler is not None:
            try:
                handler(msg)
            except Exception:  # noqa: BLE001
                log.exception("handler for %s raised", tr_cd)

    def _on_error(self, ws, err) -> None:  # noqa: ANN001
        log.warning("ws error: %s", err)

    def _on_close(self, ws, code, msg) -> None:  # noqa: ANN001
        log.info("ws closed: code=%s msg=%s", code, msg)
        self._connected.clear()

    def _send(self, payload: dict) -> None:
        if self._ws is None:
            return
        try:
            self._ws.send(json.dumps(payload, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            log.warning("ws send failed: %s", e)

    def _send_register(self, tr_cd: str, tr_key: str) -> None:
        self._send(
            {
                "header": {"token": self._auth.token, "tr_type": self.TR_REGISTER},
                "body": {"tr_cd": tr_cd, "tr_key": tr_key},
            }
        )
