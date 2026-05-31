"""Unit tests for monitor.market_hours."""

import datetime
import zoneinfo
from unittest.mock import patch

import pytest
from monitor.market_hours import is_market_hours, seconds_until_market_close, seconds_until_market_open

_KST = zoneinfo.ZoneInfo("Asia/Seoul")


def _kst(year: int, month: int, day: int, hour: int, minute: int, second: int = 0) -> datetime.datetime:
    return datetime.datetime(year, month, day, hour, minute, second, tzinfo=_KST)


# 2024-01-01 = Monday; 2024-01-06 = Saturday; 2024-01-07 = Sunday


# ---------------------------------------------------------------------------
# is_market_hours
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dt,expected",
    [
        (_kst(2024, 1, 1, 9, 0), True),  # Monday 09:00 — open
        (_kst(2024, 1, 1, 9, 0, 1), True),  # Monday 09:00:01 — open
        (_kst(2024, 1, 1, 12, 0), True),  # Monday 12:00 — mid-session
        (_kst(2024, 1, 1, 15, 29, 59), True),  # Monday 15:29:59 — still open
        (_kst(2024, 1, 1, 15, 30), True),  # Monday 15:30 — closing tick
        (_kst(2024, 1, 1, 8, 59), False),  # Monday 08:59 — pre-open
        (_kst(2024, 1, 1, 15, 31), False),  # Monday 15:31 — post-close
        (_kst(2024, 1, 5, 10, 0), True),  # Friday 10:00 — open
        (_kst(2024, 1, 6, 12, 0), False),  # Saturday — weekend
        (_kst(2024, 1, 7, 12, 0), False),  # Sunday — weekend
    ],
)
def test_is_market_hours(dt: datetime.datetime, expected: bool) -> None:
    with patch("monitor.market_hours._now_kst", return_value=dt):
        assert is_market_hours() is expected


# ---------------------------------------------------------------------------
# seconds_until_market_open
# ---------------------------------------------------------------------------


def test_seconds_until_market_open_before_open_same_day() -> None:
    # Monday 08:00 → open same day 09:00 → 3600s
    now = _kst(2024, 1, 1, 8, 0)
    with patch("monitor.market_hours._now_kst", return_value=now):
        secs = seconds_until_market_open()
    assert abs(secs - 3600) < 1


def test_seconds_until_market_open_after_open_next_day() -> None:
    # Monday 10:00 → next open Tuesday 09:00
    now = _kst(2024, 1, 1, 10, 0)
    expected = (_kst(2024, 1, 2, 9, 0) - now).total_seconds()
    with patch("monitor.market_hours._now_kst", return_value=now):
        secs = seconds_until_market_open()
    assert abs(secs - expected) < 1


def test_seconds_until_market_open_friday_after_close_skips_weekend() -> None:
    # Friday 16:00 → next open Monday 09:00 (skips Sat+Sun)
    now = _kst(2024, 1, 5, 16, 0)
    expected = (_kst(2024, 1, 8, 9, 0) - now).total_seconds()
    with patch("monitor.market_hours._now_kst", return_value=now):
        secs = seconds_until_market_open()
    assert abs(secs - expected) < 1


def test_seconds_until_market_open_saturday_skips_sunday() -> None:
    # Saturday 12:00 → next open Monday 09:00
    now = _kst(2024, 1, 6, 12, 0)
    expected = (_kst(2024, 1, 8, 9, 0) - now).total_seconds()
    with patch("monitor.market_hours._now_kst", return_value=now):
        secs = seconds_until_market_open()
    assert abs(secs - expected) < 1


def test_seconds_until_market_open_sunday() -> None:
    # Sunday 08:00 → next open Monday 09:00
    now = _kst(2024, 1, 7, 8, 0)
    expected = (_kst(2024, 1, 8, 9, 0) - now).total_seconds()
    with patch("monitor.market_hours._now_kst", return_value=now):
        secs = seconds_until_market_open()
    assert abs(secs - expected) < 1


# ---------------------------------------------------------------------------
# seconds_until_market_close
# ---------------------------------------------------------------------------


def test_seconds_until_market_close_during_session() -> None:
    # 14:00 → 90 minutes until 15:30 → 5400s
    now = _kst(2024, 1, 1, 14, 0)
    with patch("monitor.market_hours._now_kst", return_value=now):
        secs = seconds_until_market_close()
    assert abs(secs - 5400) < 1


def test_seconds_until_market_close_at_open() -> None:
    # 09:00 → 6.5 hours until 15:30 → 23400s
    now = _kst(2024, 1, 1, 9, 0)
    with patch("monitor.market_hours._now_kst", return_value=now):
        secs = seconds_until_market_close()
    assert abs(secs - 23400) < 1


def test_seconds_until_market_close_returns_zero_after_close() -> None:
    now = _kst(2024, 1, 1, 16, 0)
    with patch("monitor.market_hours._now_kst", return_value=now):
        secs = seconds_until_market_close()
    assert secs == 0.0


def test_seconds_until_market_close_returns_zero_at_exact_close() -> None:
    now = _kst(2024, 1, 1, 15, 30)
    with patch("monitor.market_hours._now_kst", return_value=now):
        secs = seconds_until_market_close()
    assert secs == 0.0
