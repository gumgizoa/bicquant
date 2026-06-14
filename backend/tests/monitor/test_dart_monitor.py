"""Tests for monitor.dart_monitor and DART notifier formatters.

Live (``slow``) tests hit the real DART API and dev Telegram chat. Pure-function
tests (formatters) and the loop scheduler tests (clock + cancellation injected —
no external service) run offline.
"""

import asyncio
import datetime
import zoneinfo
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from monitor.dart_monitor import (
    _LISTED_CLS,
    _POLL_END_PAGE,
    _check_new_disclosures,
    _fetch_disclosures,
    _is_dart_disclosure_hours,
    _matches_subject,
    _seconds_until_dart_open,
    _seen_rcept_nos,
    _send_morning_summary,
    monitor_dart_disclosures,
)
from monitor.notifier import format_dart_daily_count, format_dart_new_disclosure

_KST = zoneinfo.ZoneInfo("Asia/Seoul")


def _kst(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime.datetime:
    return datetime.datetime(year, month, day, hour, minute, second, tzinfo=_KST)


def _disc(
    rcept_no: str,
    corp_cls: str = "유",
    corp_name: str = "삼성전자",
    report_nm: str = "주요사항보고서(유상증자결정)",
) -> dict:
    return {
        "rcept_no": rcept_no,
        "corp_cls": corp_cls,
        "corp_name": corp_name,
        "report_nm": report_nm,
        "flr_nm": corp_name,
        "rcept_dt": pd.Timestamp("2026-06-02 09:30"),
        "rm": "",
    }


@pytest.fixture(autouse=True)
def _reset_seen():
    """Keep the module-global seen-set isolated between tests."""
    _seen_rcept_nos.clear()
    yield
    _seen_rcept_nos.clear()


# ---------------------------------------------------------------------------
# DART disclosure hours
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dt,expected",
    [
        (_kst(2024, 1, 1, 7, 29, 59), False),
        (_kst(2024, 1, 1, 7, 30), True),
        (_kst(2024, 1, 1, 12, 0), True),
        (_kst(2024, 1, 1, 17, 59, 59), True),
        (_kst(2024, 1, 1, 18, 0), False),
        (_kst(2024, 1, 6, 12, 0), False),
    ],
)
def test_is_dart_disclosure_hours(dt: datetime.datetime, expected: bool) -> None:
    with patch("monitor.dart_monitor._now_kst", return_value=dt):
        assert _is_dart_disclosure_hours() is expected


def test_seconds_until_dart_open_before_open_same_day() -> None:
    now = _kst(2024, 1, 1, 7, 0)
    with patch("monitor.dart_monitor._now_kst", return_value=now):
        secs = _seconds_until_dart_open()
    assert abs(secs - 1800) < 1


def test_seconds_until_dart_open_after_close_skips_weekend() -> None:
    now = _kst(2024, 1, 5, 18, 1)
    expected = (_kst(2024, 1, 8, 7, 30) - now).total_seconds()
    with patch("monitor.dart_monitor._now_kst", return_value=now):
        secs = _seconds_until_dart_open()
    assert abs(secs - expected) < 1


# ---------------------------------------------------------------------------
# format_dart_daily_count — pure function
# ---------------------------------------------------------------------------


def test_format_dart_daily_count_contains_header() -> None:
    msg = format_dart_daily_count("20260602", 0, {})
    assert "오늘 공시 현황" in msg
    assert "장 시작" in msg


def test_format_dart_daily_count_shows_date_and_total() -> None:
    msg = format_dart_daily_count("20260602", 15, {"유": 8, "코": 7})
    assert "2026-06-02" in msg
    assert "15건" in msg


def test_format_dart_daily_count_shows_breakdown() -> None:
    msg = format_dart_daily_count("20260602", 3, {"유": 2, "코": 1})
    assert "유가증권: 2건" in msg
    assert "코스닥: 1건" in msg


def test_format_dart_daily_count_empty() -> None:
    msg = format_dart_daily_count("20260602", 0, {})
    assert "0건" in msg


# ---------------------------------------------------------------------------
# format_dart_new_disclosure — pure function
# ---------------------------------------------------------------------------


def test_format_dart_new_disclosure_contains_header() -> None:
    msg = format_dart_new_disclosure(_disc("001"))
    assert "새 공시" in msg


def test_format_dart_new_disclosure_shows_company_and_report() -> None:
    msg = format_dart_new_disclosure(_disc("001", corp_cls="유", corp_name="삼성전자"))
    assert "삼성전자" in msg
    assert "유가증권" in msg
    assert "주요사항보고서" in msg


def test_format_dart_new_disclosure_shows_time() -> None:
    msg = format_dart_new_disclosure(_disc("001"))
    assert "09:30" in msg


def test_format_dart_new_disclosure_kosdaq_label() -> None:
    msg = format_dart_new_disclosure(_disc("001", corp_cls="코", corp_name="카카오"))
    assert "코스닥" in msg
    assert "카카오" in msg


# ---------------------------------------------------------------------------
# Live: _fetch_disclosures — real DART API
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_fetch_disclosures_live_returns_filtered_list(dart, recent_trading_day) -> None:
    result = await _fetch_disclosures(recent_trading_day, 5)
    assert isinstance(result, list)
    # Whatever comes back must satisfy both filters the function applies.
    for d in result:
        assert d["corp_cls"] in _LISTED_CLS
        assert _matches_subject(d["report_nm"])
        assert d["rcept_no"]


@pytest.mark.slow
async def test_fetch_disclosures_live_raw_records_have_expected_keys(dart, recent_trading_day) -> None:
    # Exercises the raw DART list endpoint (pre-filter) for schema sanity.
    from dartapi.dart_utils import list_dart_disclosures_by_date

    records = await asyncio.to_thread(list_dart_disclosures_by_date, recent_trading_day, 1, 1)
    assert isinstance(records, list)
    if records:  # a trading day normally has disclosures; tolerate a quiet day
        expected = {"rcept_dt", "corp_cls", "corp_name", "rcept_no", "report_nm", "flr_nm", "rm"}
        assert expected.issubset(records[0].keys())


# ---------------------------------------------------------------------------
# Live: _send_morning_summary / _check_new_disclosures — real DART + Telegram
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_send_morning_summary_live(dart, telegram, recent_trading_day) -> None:
    await _send_morning_summary(recent_trading_day)  # real DART fetch + real Telegram

    # The seen-set is initialised to exactly the listed/monitored disclosures.
    expected = {d["rcept_no"] for d in await _fetch_disclosures(recent_trading_day, 50)}
    assert _seen_rcept_nos == expected


@pytest.mark.slow
async def test_check_new_disclosures_live_dedups(dart, recent_trading_day) -> None:
    # Pre-seed the seen-set with everything currently published (live fetch), so
    # the poll finds nothing new: the seen-set is unchanged and no message is
    # emitted. No Telegram fixture needed — dedup is observed via the seen-set.
    current = await _fetch_disclosures(recent_trading_day, _POLL_END_PAGE)
    _seen_rcept_nos.update(d["rcept_no"] for d in current)
    snapshot = set(_seen_rcept_nos)

    await _check_new_disclosures(recent_trading_day)  # real DART fetch

    assert _seen_rcept_nos == snapshot


# ---------------------------------------------------------------------------
# monitor_dart_disclosures — scheduler loop (clock + cancellation injected).
# Not an API mock: verifies morning-summary-then-poll ordering and the
# post-close reset without looping forever.
# ---------------------------------------------------------------------------


async def test_monitor_dart_disclosures_morning_fires_once_then_polls() -> None:
    iterations = 0

    def fake_market_hours():
        nonlocal iterations
        iterations += 1
        if iterations <= 3:
            return True
        raise asyncio.CancelledError()

    with (
        patch("monitor.dart_monitor._is_dart_disclosure_hours", side_effect=fake_market_hours),
        patch("monitor.dart_monitor._send_morning_summary", new_callable=AsyncMock) as mock_morning,
        patch("monitor.dart_monitor._check_new_disclosures", new_callable=AsyncMock) as mock_poll,
        patch("monitor.dart_monitor.asyncio.sleep", new_callable=AsyncMock),
    ):
        try:
            await monitor_dart_disclosures()
        except asyncio.CancelledError:
            pass

    mock_morning.assert_awaited_once()
    assert mock_poll.await_count == 2  # iterations 2 and 3


async def test_monitor_dart_disclosures_resets_state_after_market_close() -> None:
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
        patch("monitor.dart_monitor._is_dart_disclosure_hours", side_effect=fake_market_hours),
        patch("monitor.dart_monitor._send_morning_summary", new_callable=AsyncMock) as mock_morning,
        patch("monitor.dart_monitor._check_new_disclosures", new_callable=AsyncMock),
        patch("monitor.dart_monitor._seconds_until_dart_open", return_value=0.0),
        patch("monitor.dart_monitor.asyncio.sleep", new_callable=AsyncMock),
    ):
        try:
            await monitor_dart_disclosures()
        except asyncio.CancelledError:
            pass

    assert mock_morning.await_count == 2
