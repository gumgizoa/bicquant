"""OAuth2 client-credentials token manager (synchronous)."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import requests

from lsapi.config import LSConfig
from lsapi.exceptions import LSAuthError

TOKEN_PATH = "/oauth2/token"


class TokenManager:
    """Fetches and caches the access_token used by every TR call.

    A short safety margin (30s) is applied to ``expires_in`` so a request never
    goes out with an already-expiring token. The token is cached on disk at
    ``<cache_dir>/token-<appkey>.json`` and shared across processes.
    """

    SAFETY_WINDOW = 30  # seconds

    def __init__(self, cfg: LSConfig, *, session: requests.Session | None = None) -> None:
        self._cfg = cfg
        self._session = session or requests.Session()
        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._cache_file: Path | None = None
        if cfg.cache_dir:
            cfg.cache_dir.mkdir(parents=True, exist_ok=True)
            safe_key = (cfg.appkey or "anon")[:16]
            self._cache_file = cfg.cache_dir / f"token-{safe_key}.json"
            self._load_cache()

    # ----- public ---------------------------------------------------------

    @property
    def token(self) -> str:
        with self._lock:
            if self._valid():
                return self._token  # type: ignore[return-value]
            self._refresh()
            return self._token  # type: ignore[return-value]

    def invalidate(self) -> None:
        with self._lock:
            self._token = None
            self._expires_at = 0.0
            if self._cache_file and self._cache_file.exists():
                try:
                    self._cache_file.unlink()
                except OSError:
                    pass

    # ----- internals ------------------------------------------------------

    def _valid(self) -> bool:
        return bool(self._token) and time.time() + self.SAFETY_WINDOW < self._expires_at

    def _refresh(self) -> None:
        self._cfg.ensure_credentials()
        url = self._cfg.rest_base + TOKEN_PATH
        data = {
            "appkey": self._cfg.appkey,
            "appsecretkey": self._cfg.appsecret,
            "grant_type": "client_credentials",
            "scope": self._cfg.scope,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            resp = self._session.post(url, data=data, headers=headers, timeout=self._cfg.timeout)
        except requests.RequestException as e:
            raise LSAuthError(f"token request failed: {e}") from e

        if resp.status_code >= 400:
            raise LSAuthError(f"token refusal: HTTP {resp.status_code} — {resp.text[:300]}")
        try:
            body = resp.json()
        except ValueError as e:
            raise LSAuthError(f"non-JSON token body: {resp.text[:300]}") from e

        token = body.get("access_token")
        if not token:
            raise LSAuthError(f"no access_token in response: {body}")
        expires_in = int(body.get("expires_in") or 0)
        if expires_in <= 0:
            expires_in = 86400  # LS tokens default to 1 day

        self._token = token
        self._expires_at = time.time() + expires_in
        self._save_cache()

    def _save_cache(self) -> None:
        if not self._cache_file:
            return
        try:
            self._cache_file.write_text(
                json.dumps({"access_token": self._token, "expires_at": self._expires_at}),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _load_cache(self) -> None:
        if not self._cache_file or not self._cache_file.exists():
            return
        try:
            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        tok = data.get("access_token")
        exp = float(data.get("expires_at") or 0)
        if tok and exp > time.time() + self.SAFETY_WINDOW:
            self._token = tok
            self._expires_at = exp
