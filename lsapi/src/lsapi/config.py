"""Runtime configuration for the LS Securities OpenAPI client."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_REST_BASE = "https://openapi.ls-sec.co.kr:8080"
DEFAULT_WS_URL = "wss://openapi.ls-sec.co.kr:9443/websocket"
DEFAULT_CACHE_DIR = Path.home() / ".lsapi"


@dataclass
class LSConfig:
    """Connection / authentication configuration.

    Missing credentials fall back to environment variables::

        LS_APPKEY, LS_APPSECRET, LS_REST_BASE, LS_WS_URL, LS_CACHE_DIR

    Both ``app_key``/``app_secret`` and ``appkey``/``appsecret`` spellings are
    accepted by :meth:`from_env` so existing call sites keep working.
    """

    appkey: str = ""
    appsecret: str = ""
    rest_base: str = DEFAULT_REST_BASE
    ws_url: str = DEFAULT_WS_URL
    scope: str = "oob"
    cache_dir: Path = field(default_factory=lambda: DEFAULT_CACHE_DIR)
    timeout: float = 10.0
    mac_address: str = ""
    # Transient network errors (DNS/connection/timeout) are retried this many
    # times with exponential backoff starting at ``retry_backoff`` seconds.
    max_retries: int = 3
    retry_backoff: float = 0.5

    @classmethod
    def from_env(cls, **overrides: object) -> "LSConfig":
        """Build a config from explicit overrides, then environment variables.

        ``app_key``/``app_secret`` are accepted as aliases for
        ``appkey``/``appsecret``.
        """
        if overrides.get("appkey") is None and overrides.get("app_key") is not None:
            overrides["appkey"] = overrides.pop("app_key")
        if overrides.get("appsecret") is None and overrides.get("app_secret") is not None:
            overrides["appsecret"] = overrides.pop("app_secret")
        overrides.pop("app_key", None)
        overrides.pop("app_secret", None)

        def pick(name: str, default: object) -> object:
            if name in overrides and overrides[name] is not None:
                return overrides[name]
            env = os.environ.get("LS_" + name.upper())
            return env if env else default

        return cls(
            appkey=str(pick("appkey", "")),
            appsecret=str(pick("appsecret", "")),
            rest_base=str(pick("rest_base", DEFAULT_REST_BASE)),
            ws_url=str(pick("ws_url", DEFAULT_WS_URL)),
            scope=str(pick("scope", "oob")),
            cache_dir=Path(str(pick("cache_dir", DEFAULT_CACHE_DIR))),
            timeout=float(pick("timeout", 10.0)),  # type: ignore[arg-type]
            mac_address=str(pick("mac_address", "")),
            max_retries=int(pick("max_retries", 3)),  # type: ignore[arg-type]
            retry_backoff=float(pick("retry_backoff", 0.5)),  # type: ignore[arg-type]
        )

    def ensure_credentials(self) -> None:
        if not self.appkey or not self.appsecret:
            raise ValueError("appkey/appsecret missing — pass them to LSClient or set LS_APPKEY / LS_APPSECRET environment variables.")
