"""Live tests for the AsyncLSClient facade over the sync engine."""

import os

import pytest
from dotenv import load_dotenv

from lsapi import AsyncLSClient

load_dotenv()
APP_KEY = os.environ.get("LS_OPENAPI_APP_KEY", "")
APP_SECRET = os.environ.get("LS_OPENAPI_APP_SECRET", "")
HAVE_CREDS = bool(APP_KEY and APP_SECRET)
SHCODE = "005930"

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not HAVE_CREDS, reason="LS creds not set")]


async def test_async_call_returns_quote() -> None:
    async with AsyncLSClient(app_key=APP_KEY, app_secret=APP_SECRET) as client:
        resp = await client.call("t1101", shcode=SHCODE)
        assert resp.ok
        assert resp.block("t1101OutBlock")["hname"]


async def test_async_paginate_follows_tr_cont() -> None:
    async with AsyncLSClient(app_key=APP_KEY, app_secret=APP_SECRET) as client:
        pages = []
        async for page in client.paginate("t1301", shcode=SHCODE, cvolume=0):
            assert page.ok
            pages.append(page)
            if len(pages) >= 2:  # stop early; t1301 can paginate a long time
                break
        assert pages  # at least one page returned
