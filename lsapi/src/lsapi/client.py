"""Synchronous REST client for LS Securities OpenAPI."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

import requests

from lsapi.auth import TokenManager
from lsapi.catalog import Catalog, TRSpec, default_catalog
from lsapi.config import LSConfig
from lsapi.exceptions import LSApiError, LSRateLimitError

if TYPE_CHECKING:
    from lsapi.generated import GeneratedAPI
    from lsapi.realtime import LSRealtime
    from lsapi.stock import StockAPI

log = logging.getLogger("lsapi")


@dataclass
class TRResponse:
    """Wrapper around a TR response.

    Attributes:
        tr_cd: the TR code that produced this response.
        rsp_cd: LS response code (``"00000"`` = success).
        rsp_msg: LS response message (Korean).
        body: full JSON body as returned by the gateway (including OutBlocks).
        tr_cont: ``tr_cont`` header (continuation flag, ``"Y"`` if more pages).
        tr_cont_key: ``tr_cont_key`` header (continuation key).
    """

    tr_cd: str
    rsp_cd: str
    rsp_msg: str
    body: dict
    tr_cont: str | None = None
    tr_cont_key: str | None = None

    @property
    def ok(self) -> bool:
        return self.rsp_cd in ("00000", "0", "")

    @property
    def has_next(self) -> bool:
        return (self.tr_cont or "").upper() == "Y"

    @property
    def cont_key(self) -> str:
        return self.tr_cont_key or ""

    def block(self, name: str, default: Any = None) -> Any:
        return self.body.get(name, default)

    def __getitem__(self, key: str) -> Any:
        return self.body[key]

    def __iter__(self):
        return iter(self.body.items())


class LSClient:
    """High-level synchronous client.

    ``LSClient("appkey", "secret")`` is the normal entry point. If credentials
    are not passed, they are read from ``LS_APPKEY`` / ``LS_APPSECRET``.

    Usage::

        client = LSClient(app_key="...", app_secret="...")
        client.stock.quote("005930")                 # convenience layer
        client.api.stock_quote.t1101(shcode="005930")  # generated wrappers
        client.call("t1101", shcode="005930")        # generic by TR code
    """

    def __init__(
        self,
        app_key: str | None = None,
        app_secret: str | None = None,
        *,
        config: LSConfig | None = None,
        catalog: Catalog | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config or LSConfig.from_env(app_key=app_key, app_secret=app_secret)
        self.catalog = catalog or default_catalog()
        self._session = session or requests.Session()
        self._auth = TokenManager(self.config, session=self._session)
        self._last_call: dict[str, float] = {}

        from lsapi.generated import GeneratedAPI  # late import to avoid cycle
        from lsapi.stock import StockAPI

        self.stock: StockAPI = StockAPI(self)
        self.api: GeneratedAPI = GeneratedAPI(self)

    # ------------------------------------------------------------------ TR

    def call(
        self,
        tr_cd: str,
        body: dict | None = None,
        *,
        tr_cont: str = "N",
        tr_cont_key: str = "",
        extra_headers: dict | None = None,
        **block_kwargs: Any,
    ) -> TRResponse:
        """Invoke a TR by code.

        Both forms work::

            client.call("t1101", {"t1101InBlock": {"shcode": "005930"}})
            client.call("t1101", shcode="005930")
        """
        spec = self.catalog.tr(tr_cd)
        if body is None:
            body = spec.build_body(**block_kwargs)
        elif block_kwargs:
            primary = spec.primary_in_block
            if primary is None:
                raise LSApiError(f"TR {tr_cd} has no known input block for keyword args")
            body = {**body, primary: {**body.get(primary, {}), **block_kwargs}}
        return self._dispatch(spec, body, tr_cont=tr_cont, tr_cont_key=tr_cont_key, extra_headers=extra_headers)

    def raw(
        self,
        tr_cd: str,
        body: dict,
        *,
        tr_cont: str = "N",
        tr_cont_key: str = "",
        extra_headers: dict | None = None,
    ) -> TRResponse:
        """Lower-level call — caller supplies the exact body; only the endpoint
        is looked up from the catalog."""
        spec = self.catalog.tr(tr_cd)
        return self._dispatch(spec, body, tr_cont=tr_cont, tr_cont_key=tr_cont_key, extra_headers=extra_headers)

    def paginate(
        self,
        tr_cd: str,
        body: dict | None = None,
        *,
        max_pages: int = 50,
        on_page: Callable[[TRResponse], None] | None = None,
        **block_kwargs: Any,
    ) -> list[TRResponse]:
        """Follow LS continuation headers (``tr_cont``) until exhausted.

        Stops when ``tr_cont != 'Y'`` or after ``max_pages``.
        """
        pages: list[TRResponse] = []
        tr_cont, tr_cont_key = "N", ""
        for _ in range(max_pages):
            resp = self.call(tr_cd, body, tr_cont=tr_cont, tr_cont_key=tr_cont_key, **block_kwargs)
            pages.append(resp)
            if on_page:
                on_page(resp)
            if not resp.has_next:
                break
            tr_cont, tr_cont_key = "Y", resp.cont_key
        return pages

    def realtime(self, **kwargs: Any) -> "LSRealtime":
        """Create a realtime (WebSocket) client sharing this client's auth."""
        from lsapi.realtime import LSRealtime

        return LSRealtime(config=self.config, token_manager=self._auth, **kwargs)

    def close(self) -> None:
        self._session.close()

    # ------------------------------------------------------------ internals

    def _dispatch(
        self,
        spec: TRSpec,
        body: dict,
        *,
        tr_cont: str,
        tr_cont_key: str,
        extra_headers: dict | None,
    ) -> TRResponse:
        if spec.is_realtime:
            raise LSApiError(f"{spec.code!r}는 실시간 TR입니다 — LSWebSocketClient를 사용하세요")

        if spec.tps_limit:
            min_interval = 1.0 / spec.tps_limit
            elapsed = time.monotonic() - self._last_call.get(spec.code, 0.0)
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
        self._last_call[spec.code] = time.monotonic()

        url = self.config.rest_base + spec.url
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")

        token_refreshed = False
        while True:
            headers = {
                "Content-Type": spec.content_type or "application/json; charset=UTF-8",
                "authorization": f"Bearer {self._auth.token}",
                "tr_cd": spec.code,
                "tr_cont": tr_cont or "N",
                "tr_cont_key": tr_cont_key or "",
            }
            if self.config.mac_address:
                headers["mac_address"] = self.config.mac_address
            if extra_headers:
                headers.update(extra_headers)

            log.debug("POST %s tr_cd=%s body=%s", url, spec.code, body)
            attempt = 0
            while True:
                try:
                    resp = self._session.request(
                        spec.method or "POST",
                        url,
                        headers=headers,
                        data=payload,
                        timeout=self.config.timeout,
                    )
                    break
                except requests.RequestException as e:
                    # Transient network errors (DNS failures, dropped connections,
                    # timeouts) are retried with exponential backoff before giving up.
                    attempt += 1
                    if attempt > self.config.max_retries:
                        raise LSApiError(f"[{spec.code}] network error after {attempt} attempts: {e}") from e
                    wait = self.config.retry_backoff * (2 ** (attempt - 1))
                    log.warning(
                        "[%s] network error (attempt %d/%d): %s — retrying in %.1fs",
                        spec.code,
                        attempt,
                        self.config.max_retries,
                        e,
                        wait,
                    )
                    time.sleep(wait)

            if resp.status_code == 429:
                raise LSRateLimitError(f"[{spec.code}] throughput quota exceeded", http_status=429)
            try:
                data = resp.json() if resp.content else {}
            except ValueError:
                raise LSApiError(f"[{spec.code}] non-JSON response", http_status=resp.status_code, body=resp.text)

            rsp_cd = str(data.get("rsp_cd") or "")
            rsp_msg = str(data.get("rsp_msg") or "")

            # LS gateway invalidates tokens on re-authentication: refresh once and retry.
            if rsp_cd == "IGW00121" and not token_refreshed:
                log.warning("[%s] token rejected by server (IGW00121); refreshing and retrying", spec.code)
                self._auth.invalidate()
                token_refreshed = True
                continue

            if resp.status_code >= 400 or (rsp_cd and rsp_cd not in ("00000", "0")):
                raise LSApiError(
                    f"[{spec.code}] {rsp_cd}: {rsp_msg or 'error'}",
                    rsp_cd=rsp_cd or None,
                    rsp_msg=rsp_msg or None,
                    http_status=resp.status_code,
                    body=data,
                )
            return TRResponse(
                tr_cd=spec.code,
                rsp_cd=rsp_cd,
                rsp_msg=rsp_msg,
                body=data,
                tr_cont=resp.headers.get("tr_cont"),
                tr_cont_key=resp.headers.get("tr_cont_key"),
            )
