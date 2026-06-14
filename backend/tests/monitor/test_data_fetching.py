"""Integration tests for monitor data fetching against the live LS API.

The ``slow`` tests use the shared ``ls_client`` fixture (real dev credentials);
they are skipped when credentials are absent. The deviation-ratio math tests are
pure and run offline.

Run all:          uv run pytest backend/tests/monitor/
Run unit only:    uv run pytest backend/tests/monitor/ -m "not slow"
Run integration:  uv run pytest backend/tests/monitor/ -m slow
"""

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Unit tests — deviation ratio calculation (no API calls)
# ---------------------------------------------------------------------------


def _compute_deviation(closes: list[float]) -> float:
    """Mirror of the logic in deviation.py._evaluate."""
    current = closes[-1]
    ma50 = float(np.mean(closes[-51:-1]))
    return current / ma50 * 100


def test_deviation_ratio_at_threshold():
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
@pytest.mark.parametrize(
    "shcode,floor",
    [("001", 1000.0), ("301", 100.0)],  # KOSPI, KOSDAQ
)
async def test_fetch_index_daily_chart(ls_client, shcode: str, floor: float) -> None:
    """t8419: index daily bars — shape and numeric closes."""
    resp = await ls_client.call(
        "t8419",
        {
            "t8419InBlock": {
                "shcode": shcode,
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
    assert closes[-1] > floor


@pytest.mark.slow
async def test_fetch_samsung_daily_chart(ls_client) -> None:
    """t8451: Samsung Electronics (005930) daily bars."""
    resp = await ls_client.call(
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
@pytest.mark.parametrize("upcode", ["001", "301"])  # KOSPI, KOSDAQ
async def test_fetch_current_index(ls_client, upcode: str) -> None:
    """t1511: current index level — verify response fields."""
    resp = await ls_client.call("t1511", {"t1511InBlock": {"upcode": upcode}})
    block = resp.body.get("t1511OutBlock", {})
    assert block, "t1511OutBlock must not be empty"
    price = float(block.get("pricejisu", 0))
    assert price > 0, f"Index level must be positive, got {price}"
    assert block.get("diffjisu") is not None


@pytest.mark.slow
async def test_deviation_ratio_computable_from_live_data(ls_client) -> None:
    """End-to-end: fetch KOSPI bars and verify deviation ratio is computable."""
    resp = await ls_client.call(
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
    assert 50 < ratio < 200, f"Deviation ratio {ratio:.1f} is out of plausible range"
