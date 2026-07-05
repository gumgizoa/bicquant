"""Tests for the MDD feature.

Pure metric tests (max_drawdown math) run offline. Live (``slow``) tests hit
the real LS API to verify the daily-close fetch helpers.
"""

import pytest
from bot.features.mdd import max_drawdown

# NOTE: the LS fetch helpers live in bot.main and are imported lazily inside the
# live tests below — importing bot.main initialises the Azure LLM / Telegram
# config, which the offline pure tests (max_drawdown math) must not require.

# ---------------------------------------------------------------------------
# max_drawdown — pure function
# ---------------------------------------------------------------------------


def test_max_drawdown_simple_peak_to_trough() -> None:
    # peak 100 -> trough 60 = -40%
    res = max_drawdown([100.0, 60.0])
    assert res.mdd_pct == pytest.approx(-40.0)
    assert res.peak_idx == 0
    assert res.trough_idx == 1


def test_max_drawdown_monotonic_increase_is_zero() -> None:
    res = max_drawdown([10.0, 20.0, 30.0, 40.0])
    assert res.mdd_pct == 0.0
    assert res.peak_idx == 0
    assert res.trough_idx == 0


def test_max_drawdown_uses_running_peak_not_global() -> None:
    # 100 -> 50 (-50%), then recovers to 200 -> 120 (-40%). Worst is -50%.
    res = max_drawdown([100.0, 50.0, 200.0, 120.0])
    assert res.mdd_pct == pytest.approx(-50.0)
    assert res.peak_idx == 0
    assert res.trough_idx == 1


def test_max_drawdown_later_deeper_drawdown_wins() -> None:
    # first dip -20%, second dip from a higher peak -60%
    res = max_drawdown([100.0, 80.0, 150.0, 60.0])
    assert res.mdd_pct == pytest.approx(-60.0)
    assert res.peak_idx == 2
    assert res.trough_idx == 3


def test_max_drawdown_trough_before_recovery() -> None:
    res = max_drawdown([100.0, 90.0, 70.0, 95.0])
    assert res.mdd_pct == pytest.approx(-30.0)
    assert res.trough_idx == 2


def test_max_drawdown_single_point_is_zero() -> None:
    res = max_drawdown([100.0])
    assert res.mdd_pct == 0.0


def test_max_drawdown_empty_raises() -> None:
    with pytest.raises(ValueError):
        max_drawdown([])


# ---------------------------------------------------------------------------
# Live: daily-close fetch helpers (LS API)
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_fetch_kr_daily_closes_live(ls_client) -> None:
    from bot.main import _fetch_kr_daily_closes

    series = await _fetch_kr_daily_closes("005930", 30)
    assert len(series) >= 2
    dates = [d for d, _ in series]
    assert dates == sorted(dates), "closes must be chronological (oldest first)"
    assert all(c > 0 for _, c in series)


@pytest.mark.slow
async def test_fetch_us_daily_closes_live(ls_client) -> None:
    from bot.main import _fetch_us_daily_closes

    series = await _fetch_us_daily_closes("AAPL", 30)
    assert len(series) >= 2
    dates = [d for d, _ in series]
    assert dates == sorted(dates), "closes must be chronological (oldest first)"
    assert all(c > 0 for _, c in series)
