"""Asynchronous facade over the synchronous :class:`LSClient`.

The synchronous client is the proven engine; this thin wrapper runs its blocking
calls in a worker thread (:func:`asyncio.to_thread`) so existing async callers
keep using ``await client.call(...)`` unchanged. Realtime is exposed through the
async :class:`~lsapi.ws_client.LSWebSocketClient`, which bridges the sync
realtime thread onto the event loop.

Note: the underlying ``requests.Session`` is shared across worker-thread calls.
The backend uses a single client sequentially (low concurrency), which is safe.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lsapi.catalog import Catalog
from lsapi.client import LSClient, TRResponse
from lsapi.config import LSConfig

if TYPE_CHECKING:
    from lsapi.ws_client import LSWebSocketClient


class AsyncLSClient:
    """Async wrapper around :class:`LSClient`.

    Usage::

        async with AsyncLSClient(app_key, app_secret) as client:
            resp = await client.call("t1101", shcode="005930")
            print(resp.block("t1101OutBlock"))
    """

    def __init__(
        self,
        app_key: str | None = None,
        app_secret: str | None = None,
        *,
        config: LSConfig | None = None,
        catalog: Catalog | None = None,
        mac_address: str = "",
        cache_dir: str | Path | None = None,
    ) -> None:
        if config is None:
            overrides: dict[str, Any] = {"app_key": app_key, "app_secret": app_secret}
            if mac_address:
                overrides["mac_address"] = mac_address
            if cache_dir is not None:
                overrides["cache_dir"] = str(Path(cache_dir).expanduser())
            config = LSConfig.from_env(**overrides)
        self._sync = LSClient(config=config, catalog=catalog)

    @property
    def config(self) -> LSConfig:
        return self._sync.config

    @property
    def catalog(self) -> Catalog:
        return self._sync.catalog

    async def __aenter__(self) -> "AsyncLSClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await asyncio.to_thread(self._sync.close)

    # ------------------------------------------------------------------ TR

    async def call(self, tr_cd: str, body: dict | None = None, **kwargs: Any) -> TRResponse:
        """Single TR request (kwargs form or full ``body`` form)."""
        return await asyncio.to_thread(lambda: self._sync.call(tr_cd, body, **kwargs))

    async def raw(self, tr_cd: str, body: dict, **kwargs: Any) -> TRResponse:
        return await asyncio.to_thread(lambda: self._sync.raw(tr_cd, body, **kwargs))

    async def paginate(self, tr_cd: str, body: dict | None = None, **kwargs: Any) -> AsyncIterator[TRResponse]:
        """Auto-paginate using ``tr_cont``; yields one page at a time."""
        tr_cont, tr_cont_key = "N", ""
        while True:
            resp = await asyncio.to_thread(lambda c=tr_cont, k=tr_cont_key: self._sync.call(tr_cd, body, tr_cont=c, tr_cont_key=k, **kwargs))
            yield resp
            if not resp.has_next:
                break
            tr_cont, tr_cont_key = "Y", resp.cont_key

    def realtime(self, **kwargs: Any) -> "LSWebSocketClient":
        """Return an async realtime client sharing this client's config/auth."""
        from lsapi.ws_client import LSWebSocketClient

        return LSWebSocketClient(config=self._sync.config, token_manager=self._sync._auth, **kwargs)
