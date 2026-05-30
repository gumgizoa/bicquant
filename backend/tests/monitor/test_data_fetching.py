"""Integration and unit tests for monitor data fetching.

Integration tests (marked 'slow') require real LS API credentials via env vars:
  LS_OPENAPI_APP_KEY, LS_OPENAPI_APP_SECRET

Run all:          uv run pytest backend/tests/monitor/
Run unit only:    uv run pytest backend/tests/monitor/ -m "not slow"
Run integration:  uv run pytest backend/tests/monitor/ -m slow
"""

import os

import pytest
from dotenv import load_dotenv

from lsapi import LSClient

load_dotenv()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

APP_KEY = os.getenv("LS_OPENAPI_APP_KEY", "")
APP_SECRET = os.getenv("LS_OPENAPI_APP_SECRET", "")
_has_creds = bool(APP_KEY and APP_SECRET)

requires_creds = pytest.mark.skipif(not _has_creds, reason="LS API credentials not set")


@pytest.fixture(autouse=True)
async def _rate_limit_slow(request):
    """Pause 1 s before each slow test to stay within LS API rate limits."""
    import asyncio

    if request.node.get_closest_marker("slow"):
        await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# Unit tests — deviation ratio calculation (no API calls)
# ---------------------------------------------------------------------------


def _compute_deviation(closes: list[float]) -> float:
    """Mirror of the logic in deviation.py._evaluate."""
    import numpy as np

    current = closes[-1]
    ma50 = float(np.mean(closes[-51:-1]))
    return current / ma50 * 100


def test_deviation_ratio_at_threshold():
    # MA50 = 100, current = 130 → ratio exactly 130
    closes = [100.0] * 50 + [130.0]
    assert abs(_compute_deviation(closes) - 130.0) < 0.01


def test_deviation_ratio_below_threshold():
    closes = [100.0] * 50 + [120.0]
    assert _compute_deviation(closes) < 130.0


def test_deviation_ratio_above_threshold():
    closes = [100.0] * 50 + [135.0]
    assert _compute_deviation(closes) > 130.0


# ---------------------------------------------------------------------------
# Integration tests — LS API data fetching
# ---------------------------------------------------------------------------


@pytest.mark.slow
@requires_creds
@pytest.mark.asyncio
async def test_fetch_kospi_daily_chart():
    """t8419: KOSPI daily bars — verify shape and numeric closes."""
    async with LSClient(APP_KEY, APP_SECRET) as client:
        resp = await client.call(
            "t8419",
            {
                "t8419InBlock": {
                    "shcode": "001",
                    "gubun": "2",
                    "qrycnt": 60,
                    "sdate": "",
                    "edate": "99999999",
                    "cts_date": "",
                    "comp_yn": "N",
                }
            },
        )

    bars = resp.body.get("t8419OutBlock1", [])
    assert len(bars) >= 50, f"Expected >= 50 bars, got {len(bars)}"

    closes = [float(b["close"]) for b in bars if b.get("close")]
    assert all(c > 0 for c in closes), "All closes must be positive"
    assert closes[-1] > 1000, "KOSPI should be above 1000"


@pytest.mark.slow
@requires_creds
@pytest.mark.asyncio
async def test_fetch_kosdaq_daily_chart():
    """t8419: KOSDAQ daily bars — verify shape and numeric closes."""
    async with LSClient(APP_KEY, APP_SECRET) as client:
        resp = await client.call(
            "t8419",
            {
                "t8419InBlock": {
                    "shcode": "301",
                    "gubun": "2",
                    "qrycnt": 60,
                    "sdate": "",
                    "edate": "99999999",
                    "cts_date": "",
                    "comp_yn": "N",
                }
            },
        )

    bars = resp.body.get("t8419OutBlock1", [])
    assert len(bars) >= 50, f"Expected >= 50 bars, got {len(bars)}"

    closes = [float(b["close"]) for b in bars if b.get("close")]
    assert all(c > 0 for c in closes)


@pytest.mark.slow
@requires_creds
@pytest.mark.asyncio
async def test_fetch_samsung_daily_chart():
    """t8451: Samsung Electronics (005930) daily bars."""
    async with LSClient(APP_KEY, APP_SECRET) as client:
        resp = await client.call(
            "t8451",
            {
                "t8451InBlock": {
                    "shcode": "005930",
                    "gubun": "2",
                    "qrycnt": 60,
                    "sdate": "",
                    "edate": "99999999",
                    "cts_date": "",
                    "comp_yn": "N",
                    "sujung": "1",
                    "exchgubun": "K",
                }
            },
        )

    bars = resp.body.get("t8451OutBlock1", [])
    assert len(bars) >= 50, f"Expected >= 50 bars, got {len(bars)}"

    closes = [float(b["close"]) for b in bars if b.get("close")]
    assert all(c > 0 for c in closes)


@pytest.mark.slow
@requires_creds
@pytest.mark.asyncio
async def test_fetch_current_kospi_index():
    """t1511: Current KOSPI index level — verify response fields."""
    async with LSClient(APP_KEY, APP_SECRET) as client:
        resp = await client.call("t1511", {"t1511InBlock": {"upcode": "001"}})

    block = resp.body.get("t1511OutBlock", {})
    assert block, "t1511OutBlock must not be empty"

    price = float(block.get("pricejisu", 0))
    assert price > 0, f"Current KOSPI index must be positive, got {price}"

    change_pct = block.get("diffjisu")
    assert change_pct is not None, "diffjisu field must be present"


@pytest.mark.slow
@requires_creds
@pytest.mark.asyncio
async def test_fetch_current_kosdaq_index():
    """t1511: Current KOSDAQ index level."""
    async with LSClient(APP_KEY, APP_SECRET) as client:
        resp = await client.call("t1511", {"t1511InBlock": {"upcode": "301"}})

    block = resp.body.get("t1511OutBlock", {})
    price = float(block.get("pricejisu", 0))
    assert price > 0, f"Current KOSDAQ index must be positive, got {price}"


@pytest.mark.slow
@requires_creds
@pytest.mark.asyncio
async def test_deviation_ratio_computable_from_live_data():
    """End-to-end: fetch KOSPI bars and verify deviation ratio is computable."""
    import numpy as np

    async with LSClient(APP_KEY, APP_SECRET) as client:
        resp = await client.call(
            "t8419",
            {
                "t8419InBlock": {
                    "shcode": "001",
                    "gubun": "2",
                    "qrycnt": 60,
                    "sdate": "",
                    "edate": "99999999",
                    "cts_date": "",
                    "comp_yn": "N",
                }
            },
        )

    bars = resp.body.get("t8419OutBlock1", [])
    closes = [float(b["close"]) for b in bars if b.get("close")]

    assert len(closes) >= 51, "Need at least 51 data points to compute MA50"

    current = closes[-1]
    ma50 = float(np.mean(closes[-51:-1]))
    ratio = current / ma50 * 100

    print(f"\nKOSPI deviation ratio: {ratio:.2f}% (current={current:.2f}, MA50={ma50:.2f})")
    assert 50 < ratio < 200, f"Deviation ratio {ratio:.1f} is out of plausible range"
