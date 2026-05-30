"""LS Securities OpenAPI REST client."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import httpx

from lsapi.auth import TokenManager
from lsapi.catalog import Catalog, TRSpec, default_catalog
from lsapi.exceptions import LSApiError

_BASE_URL = "https://openapi.ls-sec.co.kr:8080"


@dataclass
class TRResponse:
    tr_cd: str
    rsp_cd: str
    rsp_msg: str
    body: dict  # full server response, including OutBlocks
    has_next: bool  # tr_cont == "Y"
    cont_key: str  # tr_cont_key to use in the next continuation request

    @property
    def ok(self) -> bool:
        """True if rsp_cd indicates success."""
        return self.rsp_cd in ("00000", "0", "")

    def block(self, name: str) -> list | dict | None:
        """Access the response body by OutBlock name, returning None if absent."""
        return self.body.get(name)


class LSClient:
    """Async REST client for LS Securities OpenAPI.

    Usage:
        async with LSClient(app_key, app_secret) as client:
            resp = await client.call("t1101", shcode="005930")
            print(resp.block("t1101OutBlock")["price"])

    token cache:
        async with LSClient(app_key, app_secret, cache_dir=Path("~/.lsapi").expanduser()) as client:
            ...
    """

    def __init__(
        self,
        app_key: str,
        app_secret: str,
        *,
        catalog: Catalog | None = None,
        mac_address: str = "",
        cache_dir: str | Path | None = None,
    ) -> None:
        _cache = Path(cache_dir).expanduser() if cache_dir else None
        self._tokens = TokenManager(app_key, app_secret, cache_dir=_cache)
        self._http = httpx.AsyncClient(base_url=_BASE_URL, timeout=30.0)
        self._catalog = catalog or default_catalog()
        self._mac = mac_address

    async def __aenter__(self) -> "LSClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def call(self, tr_cd: str, **kwargs: object) -> TRResponse:
        """Single TR request. kwargs are mapped to the first InBlock fields.

        Example:
            await client.call("t1101", shcode="005930")
        """
        spec = self._catalog.tr(tr_cd)
        _assert_not_realtime(spec)
        return await self._post(spec, self._build_body(spec, kwargs))

    async def paginate(self, tr_cd: str, **kwargs: object) -> AsyncIterator[TRResponse]:
        """Auto-paginate using tr_cont.

        Example:
            async for page in client.paginate("t1301", shcode="005930", ...):
                rows = page.block("t1301OutBlock1")
        """
        spec = self._catalog.tr(tr_cd)
        _assert_not_realtime(spec)
        body = self._build_body(spec, kwargs)
        cont, cont_key = "N", ""
        while True:
            resp = await self._post(spec, body, tr_cont=cont, tr_cont_key=cont_key)
            yield resp
            if not resp.has_next:
                break
            cont, cont_key = "Y", resp.cont_key

    async def raw(self, tr_cd: str, body: dict) -> TRResponse:
        """Low-level call with an explicitly provided request body.

        Example:
            await client.raw("t2106", {
                "t2106InBlock": {"code": "101R3", "nrec": 2},
                "t2106InBlock1": [{"indx": 0, ...}, {"indx": 1, ...}],
            })
        """
        spec = self._catalog.tr(tr_cd)
        return await self._post(spec, body)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_body(self, spec: TRSpec, kwargs: dict) -> dict:
        block = spec.first_in_block()
        if not block:
            return {}
        return {block.name: kwargs}

    async def _post(
        self,
        spec: TRSpec,
        body: dict,
        *,
        tr_cont: str = "N",
        tr_cont_key: str = "",
    ) -> TRResponse:
        token = await self._tokens.get()
        resp = await self._http.post(
            spec.url,
            headers={
                "authorization": f"Bearer {token}",
                "content-type": "application/json; charset=utf-8",
                "tr_cd": spec.code,
                "tr_cont": tr_cont,
                "tr_cont_key": tr_cont_key,
                "mac_address": self._mac,
            },
            json=body,
        )
        if resp.status_code != 200:
            raise LSApiError(f"[{spec.code}] HTTP {resp.status_code}: {resp.text}")
        data = resp.json()
        rsp_cd = str(data.get("rsp_cd") or "")
        if rsp_cd and rsp_cd not in ("00000", "0"):
            raise LSApiError(f"[{spec.code}] {rsp_cd}: {data.get('rsp_msg', '')}")
        return TRResponse(
            tr_cd=spec.code,
            rsp_cd=rsp_cd,
            rsp_msg=data.get("rsp_msg", ""),
            body=data,
            has_next=resp.headers.get("tr_cont", "") == "Y",
            cont_key=resp.headers.get("tr_cont_key", ""),
        )


def _assert_not_realtime(spec: TRSpec) -> None:
    if spec.is_realtime:
        raise LSApiError(f"{spec.code!r}는 실시간 TR입니다 — LSWebSocketClient를 사용하세요")
