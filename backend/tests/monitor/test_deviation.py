"""Tests for monitor.deviation.

Live (``slow``) tests hit the real LS API, dev Postgres, and dev Telegram chat.
Pure-logic tests (deviation ratio math, summary formatting) and the loop
scheduler tests (clock + cancellation injected — no external service involved)
run offline.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from monitor.deviation import (
    _evaluate,
    _fetch_adr,
    _fetch_index_closes,
    _fetch_stock_closes,
    _fetch_stock_name,
    _max_drawdown_pct,
    _run_summary,
    monitor_deviation,
)
from monitor.notifier import format_adr_summary, format_deviation_summary, format_mdd_summary
from shared.models import DeviationAlert


def _closes(ratio: float, ma50: float = 100.0) -> list[float]:
    """Build a closes list where MA50 == ma50 and current/MA50*100 == ratio."""
    return [ma50] * 50 + [ma50 * ratio / 100]


# ---------------------------------------------------------------------------
# Live: LS API data fetching
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("upcode", ["001", "301"])
async def test_fetch_index_closes_live(ls_client, upcode: str) -> None:
    closes = await _fetch_index_closes(ls_client, upcode)
    assert len(closes) >= 51, f"need >=51 bars to compute MA50, got {len(closes)}"
    assert all(c > 0 for c in closes)


@pytest.mark.slow
async def test_fetch_stock_closes_live(ls_client) -> None:
    closes = await _fetch_stock_closes(ls_client, "005930")
    assert len(closes) >= 51
    assert all(c > 0 for c in closes)


@pytest.mark.slow
async def test_fetch_stock_name_live(ls_client) -> None:
    name = await _fetch_stock_name(ls_client, "005930")
    assert name == "삼성전자"


@pytest.mark.slow
@pytest.mark.parametrize("upcode", ["001", "301"])
async def test_fetch_adr_live(ls_client, upcode: str) -> None:
    adr = await _fetch_adr(ls_client, upcode, period=20)
    assert adr is not None and adr > 0


# ---------------------------------------------------------------------------
# _fetch_adr — math with a mocked client (no LS/network)
# ---------------------------------------------------------------------------


def _adr_client(rows: list[dict]) -> AsyncMock:
    """Build a mock AsyncLSClient whose t1514 call returns `rows`."""
    resp = MagicMock()
    resp.block.return_value = rows
    client = AsyncMock()
    client.call.return_value = resp
    return client


async def test_fetch_adr_computes_ratio() -> None:
    # advances: 60+40=100, declines: 30+20=50 -> ADR = 100 * 100/50 = 200
    rows = [
        {"date": "20260101", "high": "60", "low": "30"},
        {"date": "20260102", "high": "40", "low": "20"},
    ]
    adr = await _fetch_adr(_adr_client(rows), "001", period=20)
    assert adr == pytest.approx(200.0)


async def test_fetch_adr_takes_most_recent_period() -> None:
    # oldest row (advances=999) must be dropped when period=2
    rows = [
        {"date": "20251230", "high": "999", "low": "1"},
        {"date": "20260101", "high": "60", "low": "30"},
        {"date": "20260102", "high": "40", "low": "20"},
    ]
    adr = await _fetch_adr(_adr_client(rows), "001", period=2)
    assert adr == pytest.approx(200.0)


async def test_fetch_adr_returns_none_when_no_declines() -> None:
    rows = [{"date": "20260101", "high": "10", "low": "0"}]
    assert await _fetch_adr(_adr_client(rows), "001", period=20) is None


async def test_fetch_adr_returns_none_when_empty() -> None:
    assert await _fetch_adr(_adr_client([]), "001", period=20) is None


# ---------------------------------------------------------------------------
# Live: _evaluate end-to-end (LS not needed — synthetic closes; real DB + Telegram)
# ---------------------------------------------------------------------------

_TEST_CODE = "TST_DEV"


@pytest.mark.slow
async def test_evaluate_above_threshold_writes_alert(live_db, telegram) -> None:
    before = await live_db.max_id(DeviationAlert)
    try:
        await _evaluate(_TEST_CODE, "테스트종목", _closes(131.0, ma50=50_000.0))

        rows = await live_db.rows_after(DeviationAlert, before)
        assert len(rows) == 1
        row = rows[0]
        assert row.target_code == _TEST_CODE
        assert abs(float(row.deviation_ratio) - 131.0) < 0.01
        assert abs(float(row.current_value) - 65_500.0) < 1
    finally:
        await live_db.delete_after(DeviationAlert, before)


@pytest.mark.slow
async def test_evaluate_below_threshold_writes_nothing(live_db) -> None:
    before = await live_db.max_id(DeviationAlert)
    try:
        await _evaluate(_TEST_CODE, "테스트종목", _closes(120.0))

        rows = await live_db.rows_after(DeviationAlert, before)
        assert rows == []
    finally:
        await live_db.delete_after(DeviationAlert, before)


# ---------------------------------------------------------------------------
# _evaluate guard clauses — return early before any external call (offline)
# ---------------------------------------------------------------------------


async def test_evaluate_skips_when_data_insufficient() -> None:
    # 50 points (<51) → returns before touching DB/Telegram.
    await _evaluate("001", "코스피", [100.0] * 50)


async def test_evaluate_skips_when_ma50_is_zero() -> None:
    # MA50 == 0 → returns before touching DB/Telegram.
    await _evaluate("001", "코스피", [0.0] * 50 + [130.0])


# ---------------------------------------------------------------------------
# Live: _run_summary — real LS + watchlist (DB) + Telegram
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_run_eod_summary_live(ls_client, live_db, telegram) -> None:
    # Sends a real summary message for the two indices (+ any active watchlist
    # stocks) to the dev chat. Asserts the whole pipeline completes.
    # live_db must be requested so watchlist_q.get_active_codes() has an engine.
    await _run_summary(ls_client, label="테스트 요약")


# ---------------------------------------------------------------------------
# monitor_deviation — scheduler sequencing (clock + cancellation injected).
# Not an API mock: these verify summary-label ordering without looping forever.
# ---------------------------------------------------------------------------


def _make_ls_mock() -> MagicMock:
    mock_client = AsyncMock()
    mock_ls_instance = MagicMock()
    mock_ls_instance.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ls_instance.__aexit__ = AsyncMock(return_value=False)
    return mock_ls_instance


def _make_cfg_mock() -> MagicMock:
    mock_cfg = MagicMock()
    mock_cfg.ls_api.app_key = "test_key"
    mock_cfg.ls_api.app_secret = "test_secret"
    return mock_cfg


async def test_monitor_deviation_startup_summary_fires_before_loop() -> None:
    call_count = 0

    def fake_market_hours():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return False
        raise asyncio.CancelledError()

    with (
        patch("monitor.deviation.cfg", _make_cfg_mock()),
        patch("monitor.deviation.LSClient", return_value=_make_ls_mock()),
        patch("monitor.deviation.is_market_hours", side_effect=fake_market_hours),
        patch("monitor.deviation._run_summary", new_callable=AsyncMock) as mock_summary,
        patch("monitor.deviation.seconds_until_market_open", return_value=0.0),
        patch("monitor.deviation.seconds_until_market_close", return_value=0.0),
        patch("monitor.deviation.asyncio.sleep", new_callable=AsyncMock),
    ):
        try:
            await monitor_deviation()
        except asyncio.CancelledError:
            pass

    assert mock_summary.await_count == 1
    assert mock_summary.call_args.kwargs["label"] == "서비스 시작"


async def test_monitor_deviation_morning_summary_fires_when_starting_outside_market() -> None:
    sequence = [False, False, True, True]
    idx = 0

    def fake_market_hours():
        nonlocal idx
        if idx >= len(sequence):
            raise asyncio.CancelledError()
        val = sequence[idx]
        idx += 1
        return val

    with (
        patch("monitor.deviation.cfg", _make_cfg_mock()),
        patch("monitor.deviation.LSClient", return_value=_make_ls_mock()),
        patch("monitor.deviation.is_market_hours", side_effect=fake_market_hours),
        patch("monitor.deviation._run_summary", new_callable=AsyncMock) as mock_summary,
        patch("monitor.deviation.seconds_until_market_open", return_value=0.0),
        patch("monitor.deviation.seconds_until_market_close", return_value=0.0),
        patch("monitor.deviation.asyncio.sleep", new_callable=AsyncMock),
    ):
        try:
            await monitor_deviation()
        except asyncio.CancelledError:
            pass

    assert mock_summary.await_count == 2
    labels = [c.kwargs.get("label", "장 마감") for c in mock_summary.await_args_list]
    assert labels == ["서비스 시작", "장 시작"]


async def test_monitor_deviation_morning_summary_resets_after_close() -> None:
    sequence = [True, False, False, True]
    idx = 0

    def fake_market_hours():
        nonlocal idx
        if idx >= len(sequence):
            raise asyncio.CancelledError()
        val = sequence[idx]
        idx += 1
        return val

    with (
        patch("monitor.deviation.cfg", _make_cfg_mock()),
        patch("monitor.deviation.LSClient", return_value=_make_ls_mock()),
        patch("monitor.deviation.is_market_hours", side_effect=fake_market_hours),
        patch("monitor.deviation._run_summary", new_callable=AsyncMock) as mock_summary,
        patch("monitor.deviation.seconds_until_market_open", return_value=0.0),
        patch("monitor.deviation.seconds_until_market_close", return_value=0.0),
        patch("monitor.deviation.asyncio.sleep", new_callable=AsyncMock),
    ):
        try:
            await monitor_deviation()
        except asyncio.CancelledError:
            pass

    assert mock_summary.await_count == 3
    labels = [c.kwargs.get("label", "장 마감") for c in mock_summary.await_args_list]
    assert labels == ["서비스 시작", "장 마감", "장 시작"]


# ---------------------------------------------------------------------------
# format_deviation_summary — pure function
# ---------------------------------------------------------------------------


def test_format_deviation_summary_contains_header() -> None:
    msg = format_deviation_summary([], threshold=130.0)
    assert "이격도 일일 요약" in msg


def test_format_deviation_summary_highlights_entry_above_threshold() -> None:
    entries = [{"code": "005930", "name": "삼성전자", "current": 70_000.0, "ma50": 50_000.0, "ratio": 140.0}]
    msg = format_deviation_summary(entries, threshold=130.0)
    assert "⚠️" in msg
    assert "<b>140.0</b>" in msg
    assert "삼성전자" in msg


def test_format_deviation_summary_no_highlight_below_threshold() -> None:
    entries = [{"code": "005930", "name": "삼성전자", "current": 60_000.0, "ma50": 50_000.0, "ratio": 120.0}]
    msg = format_deviation_summary(entries, threshold=130.0)
    assert "⚠️" not in msg
    assert "120.0" in msg


def test_format_deviation_summary_highlights_at_exact_threshold() -> None:
    entries = [{"code": "001", "name": "코스피", "current": 130.0, "ma50": 100.0, "ratio": 130.0}]
    msg = format_deviation_summary(entries, threshold=130.0)
    assert "⚠️" in msg


def test_format_deviation_summary_shows_all_entries() -> None:
    entries = [
        {"code": "001", "name": "코스피", "current": 105.0, "ma50": 100.0, "ratio": 105.0},
        {"code": "005930", "name": "삼성전자", "current": 140.0, "ma50": 100.0, "ratio": 140.0},
    ]
    msg = format_deviation_summary(entries, threshold=130.0)
    assert "코스피" in msg
    assert "삼성전자" in msg


def test_format_deviation_summary_default_label_is_eod() -> None:
    msg = format_deviation_summary([], threshold=130.0)
    assert "장 마감" in msg


def test_format_deviation_summary_custom_label() -> None:
    msg = format_deviation_summary([], threshold=130.0, label="장 시작")
    assert "장 시작" in msg
    assert "장 마감" not in msg


# ---------------------------------------------------------------------------
# format_adr_summary — pure function
# ---------------------------------------------------------------------------


def test_format_adr_summary_contains_header() -> None:
    msg = format_adr_summary([], overbought=120.0, oversold=75.0)
    assert "ADR 일일 요약" in msg


def test_format_adr_summary_flags_overbought() -> None:
    entries = [{"code": "001", "name": "코스피", "adr": 125.0}]
    msg = format_adr_summary(entries, overbought=120.0, oversold=75.0)
    assert "⚠️" in msg
    assert "과열" in msg
    assert "<b>125.0</b>" in msg


def test_format_adr_summary_flags_oversold() -> None:
    entries = [{"code": "301", "name": "코스닥", "adr": 70.0}]
    msg = format_adr_summary(entries, overbought=120.0, oversold=75.0)
    assert "🔻" in msg
    assert "바닥" in msg


def test_format_adr_summary_neutral_not_flagged() -> None:
    entries = [{"code": "001", "name": "코스피", "adr": 100.0}]
    msg = format_adr_summary(entries, overbought=120.0, oversold=75.0)
    assert "⚠️" not in msg
    assert "🔻" not in msg
    assert "100.0" in msg


def test_format_adr_summary_custom_label() -> None:
    msg = format_adr_summary([], overbought=120.0, oversold=75.0, label="장 시작")
    assert "장 시작" in msg
    assert "장 마감" not in msg


# ---------------------------------------------------------------------------
# _max_drawdown_pct — pure function
# ---------------------------------------------------------------------------


def test_max_drawdown_pct_simple_peak_to_trough() -> None:
    assert _max_drawdown_pct([100.0, 60.0]) == pytest.approx(-40.0)


def test_max_drawdown_pct_monotonic_increase_is_zero() -> None:
    assert _max_drawdown_pct([10.0, 20.0, 30.0]) == 0.0


def test_max_drawdown_pct_uses_running_peak_not_global() -> None:
    # 100 -> 50 (-50%), recovers to 200 -> 120 (-40%); worst is -50%
    assert _max_drawdown_pct([100.0, 50.0, 200.0, 120.0]) == pytest.approx(-50.0)


def test_max_drawdown_pct_empty_is_zero() -> None:
    assert _max_drawdown_pct([]) == 0.0


# ---------------------------------------------------------------------------
# format_mdd_summary — pure function
# ---------------------------------------------------------------------------


def test_format_mdd_summary_contains_header_with_period() -> None:
    msg = format_mdd_summary([], alert_threshold=-20.0, period=60)
    assert "MDD 일일 요약" in msg
    assert "60 거래일" in msg


def test_format_mdd_summary_flags_entry_at_or_below_threshold() -> None:
    entries = [{"code": "005930", "name": "삼성전자", "mdd": -25.3}]
    msg = format_mdd_summary(entries, alert_threshold=-20.0, period=60)
    assert "⚠️" in msg
    assert "<b>-25.3%</b>" in msg
    assert "삼성전자" in msg


def test_format_mdd_summary_no_flag_above_threshold() -> None:
    entries = [{"code": "035720", "name": "카카오", "mdd": -12.1}]
    msg = format_mdd_summary(entries, alert_threshold=-20.0, period=60)
    assert "⚠️" not in msg
    assert "-12.1%" in msg


def test_format_mdd_summary_flags_at_exact_threshold() -> None:
    entries = [{"code": "005930", "name": "삼성전자", "mdd": -20.0}]
    msg = format_mdd_summary(entries, alert_threshold=-20.0, period=60)
    assert "⚠️" in msg


def test_format_mdd_summary_custom_label() -> None:
    msg = format_mdd_summary([], alert_threshold=-20.0, period=60, label="장 시작")
    assert "장 시작" in msg
    assert "장 마감" not in msg
