"""LS Securities Open API client.

Synchronous, batteries-included client (the proven engine)::

    from lsapi import LSClient

    client = LSClient(app_key="...", app_secret="...")
    client.stock.quote("005930")                    # convenience layer
    client.api.stock_quote.t1101(shcode="005930")   # generated wrappers
    client.call("t1101", shcode="005930")           # generic by TR code

Async facade for asyncio callers (wraps the sync engine via a worker thread)::

    from lsapi import AsyncLSClient, LSWebSocketClient

    async with AsyncLSClient() as client:
        resp = await client.call("t1101", shcode="005930")

    async with LSWebSocketClient() as ws:
        await ws.subscribe("S3_", "005930", callback=on_tick)
"""

from lsapi.aio import AsyncLSClient
from lsapi.catalog import (
    BlockSpec,
    Catalog,
    FieldSpec,
    TRSpec,
    default_catalog,
)
from lsapi.client import LSClient, TRResponse
from lsapi.config import LSConfig
from lsapi.exceptions import (
    LSApiError,
    LSAuthError,
    LSRateLimitError,
    LSSpecError,
)
from lsapi.realtime import LSRealtime
from lsapi.realtime_topics import REALTIME_TOPICS, list_topics
from lsapi.ws_client import LSWebSocketClient

__all__ = [
    # clients
    "LSClient",
    "AsyncLSClient",
    "LSRealtime",
    "LSWebSocketClient",
    "TRResponse",
    # config / catalog
    "LSConfig",
    "Catalog",
    "TRSpec",
    "BlockSpec",
    "FieldSpec",
    "default_catalog",
    "REALTIME_TOPICS",
    "list_topics",
    # errors
    "LSApiError",
    "LSAuthError",
    "LSRateLimitError",
    "LSSpecError",
]

__version__ = "0.2.0"
