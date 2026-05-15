"""LS Securities OpenAPI REST client."""

import httpx

from lsapi.auth import TokenManager
from lsapi.exceptions import LSApiError

_BASE_URL = "https://openapi.ls-sec.co.kr:8080"


class LSClient:
    """Async REST client for LS Securities OpenAPI.

    Usage:
        async with LSClient(app_key, app_secret) as client:
            result = await client.request("t1101", {"shcode": "005930"})
    """

    def __init__(self, app_key: str, app_secret: str) -> None:
        self._tokens = TokenManager(app_key, app_secret)
        self._http = httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0)

    async def __aenter__(self) -> "LSClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._http.aclose()

    async def request(self, tr_cd: str, path: str, body: dict) -> dict:
        """Send a REST request.

        Args:
            tr_cd: Transaction code (e.g. "t1101").
            path: API path (e.g. "/stock/market-data").
            body: Request body dict.
        """
        token = await self._tokens.get()
        resp = await self._http.post(
            path,
            headers={
                "authorization": f"Bearer {token}",
                "content-type": "application/json; charset=utf-8",
                "tr_cd": tr_cd,
                "tr_cont": "N",
                "tr_cont_key": "",
                "mac_address": "",
            },
            json=body,
        )
        if resp.status_code != 200:
            raise LSApiError(f"[{tr_cd}] HTTP {resp.status_code}: {resp.text}")
        data = resp.json()
        if data.get("rsp_cd") not in ("00000", None):
            raise LSApiError(f"[{tr_cd}] API error {data.get('rsp_cd')}: {data.get('rsp_msg')}")
        return data
