"""OAuth2 token management for LS Securities OpenAPI."""

import time

import httpx

from lsapi.exceptions import AuthError

_TOKEN_URL = "https://openapi.ls-sec.co.kr:8080/oauth2/token"


class TokenManager:
    def __init__(self, app_key: str, app_secret: str) -> None:
        self._app_key = app_key
        self._app_secret = app_secret
        self._token: str | None = None
        self._expires_at: float = 0.0

    async def get(self) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        await self._refresh()
        assert self._token is not None
        return self._token

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
