"""Live tests for the async LSWebSocketClient against the real LS endpoint.

These verify the full path: connect → subscribe (token in register frame) →
frame delivered from the sync engine thread, bridged onto the asyncio loop.
Read-only subscriptions only. The market may be closed, in which case only the
registration ack frame is received — which is enough to prove the bridge works.
"""

import asyncio
import os

import pytest
from dotenv import load_dotenv

from lsapi import LSWebSocketClient

load_dotenv()
APP_KEY = os.environ.get("LS_OPENAPI_APP_KEY", "")
APP_SECRET = os.environ.get("LS_OPENAPI_APP_SECRET", "")
HAVE_CREDS = bool(APP_KEY and APP_SECRET)
SHCODE = "005930"

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not HAVE_CREDS, reason="LS creds not set")]


async def test_subscribe_receives_frame_bridged_to_loop() -> None:
    frames: list[dict] = []

    async with LSWebSocketClient(app_key=APP_KEY, app_secret=APP_SECRET) as ws:
        await ws.subscribe("JIF", "", callback=frames.append)  # 장운영정보
        await ws.subscribe("S3_", SHCODE, callback=frames.append)  # KOSPI 체결
        for _ in range(20):  # wait up to ~10s for any frame (ack or tick)
            if frames:
                break
            await asyncio.sleep(0.5)
        await ws.unsubscribe("S3_", SHCODE)

    assert frames, "expected at least the registration ack frame"
    assert "header" in frames[0]


async def test_connect_and_close_clean() -> None:
    ws = LSWebSocketClient(app_key=APP_KEY, app_secret=APP_SECRET)
    await ws.connect()
    assert ws._rt is not None
    await ws.close()
    assert ws._rt is None
