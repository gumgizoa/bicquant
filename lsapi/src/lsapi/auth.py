"""OAuth2 token management for LS Securities OpenAPI."""

import hashlib
import json
import time
from pathlib import Path

import httpx

from lsapi.exceptions import AuthError

_TOKEN_URL = "https://openapi.ls-sec.co.kr:8080/oauth2/token"


class TokenManager:
    def __init__(
        self,
        app_key: str,
        app_secret: str,
        *,
        cache_dir: Path | None = None,
    ) -> None:
        self._app_key = app_key
        self._app_secret = app_secret
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._cache_file: Path | None = None
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
            key_hash = hashlib.sha256(app_key.encode()).hexdigest()[:16]
            self._cache_file = cache_dir / f"token-{key_hash}.json"
            self._load_cache()

    async def get(self) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        await self._refresh()
        assert self._token is not None
        return self._token

    def _load_cache(self) -> None:
        if not self._cache_file or not self._cache_file.exists():
            return
        try:
            data = json.loads(self._cache_file.read_text(encoding="utf-8"))
            self._token = data["access_token"]
            self._expires_at = float(data["expires_at"])
        except Exception:
            pass

    def _save_cache(self) -> None:
        if self._cache_file and self._token:
            self._cache_file.write_text(
                json.dumps({"access_token": self._token, "expires_at": self._expires_at}),
                encoding="utf-8",
            )

    async def _refresh(self) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "appkey": self._app_key,
                    "appsecretkey": self._app_secret,
                    "scope": "oob",
                },
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code != 200:
            raise AuthError(f"Token refresh failed [{resp.status_code}]: {resp.text}")
        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = time.time() + int(data.get("expires_in", 86400))
        self._save_cache()
