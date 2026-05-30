"""Unit tests for monitor.deviation — _evaluate and _is_market_hours."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from monitor.deviation import _evaluate, _is_market_hours

KST = timezone(timedelta(hours=9))

# 2024-01-01 is a Monday; days 1-7 cover Mon-Sun.
_BASE = datetime(2024, 1, 1, tzinfo=KST)


def _kst(weekday: int, hour: int, minute: int) -> datetime:
    return _BASE.replace(day=1 + weekday, hour=hour, minute=minute)


def _closes(ratio: float, ma50: float = 100.0) -> list[float]:
    """Build a closes list where MA50 == ma50 and current/MA50*100 == ratio."""
    return [ma50] * 50 + [ma50 * ratio / 100]


# ---------------------------------------------------------------------------
# _is_market_hours
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "weekday,hour,minute,expected",
    [
        (0, 9, 0, True),  # Monday 09:00 — open
        (0, 12, 0, True),  # Monday 12:00 — mid-session
        (0, 15, 30, True),  # Monday 15:30 — closing tick
        (0, 8, 59, False),  # Monday 08:59 — before open
        (0, 15, 31, False),  # Monday 15:31 — after close
        (4, 10, 0, True),  # Friday 10:00 — open
        (5, 12, 0, False),  # Saturday — weekend
        (6, 12, 0, False),  # Sunday — weekend
    ],
)
def test_is_market_hours(weekday: int, hour: int, minute: int, expected: bool) -> None:
    with patch("monitor.deviation.datetime") as mock_dt:
        mock_dt.now.return_value = _kst(weekday, hour, minute)
        assert _is_market_hours() is expected


# ---------------------------------------------------------------------------
# _evaluate — alert logic
# ---------------------------------------------------------------------------


async def test_evaluate_fires_alert_above_threshold() -> None:
    with (
        patch("monitor.deviation.deviation_q.save_alert", new_callable=AsyncMock) as mock_save,
        patch("monitor.deviation.notifier.format_deviation_alert", return_value="msg") as mock_fmt,
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        await _evaluate("001", "코스피", _closes(131.0))

    mock_save.assert_awaited_once()
    mock_fmt.assert_called_once()
    mock_send.assert_awaited_once_with("msg")


async def test_evaluate_fires_at_exact_threshold() -> None:
    with (
        patch("monitor.deviation.deviation_q.save_alert", new_callable=AsyncMock) as mock_save,
        patch("monitor.deviation.notifier.format_deviation_alert", return_value="msg"),
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        await _evaluate("001", "코스피", _closes(130.0))

    mock_save.assert_awaited_once()
    mock_send.assert_awaited_once()


async def test_evaluate_no_alert_below_threshold() -> None:
    with (
        patch("monitor.deviation.deviation_q.save_alert", new_callable=AsyncMock) as mock_save,
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        await _evaluate("001", "코스피", _closes(129.9))

    mock_save.assert_not_called()
    mock_send.assert_not_called()


async def test_evaluate_skips_when_data_insufficient() -> None:
    closes = [100.0] * 50  # 50 points — need 51
    with (
        patch("monitor.deviation.deviation_q.save_alert", new_callable=AsyncMock) as mock_save,
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        await _evaluate("001", "코스피", closes)

    mock_save.assert_not_called()
    mock_send.assert_not_called()


async def test_evaluate_skips_when_ma50_is_zero() -> None:
    closes = [0.0] * 50 + [130.0]
    with (
        patch("monitor.deviation.deviation_q.save_alert", new_callable=AsyncMock) as mock_save,
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        await _evaluate("001", "코스피", closes)

    mock_save.assert_not_called()
    mock_send.assert_not_called()


async def test_evaluate_save_alert_receives_correct_values() -> None:
    """Verify that save_alert is called with the right code, name, and ratio."""
    with (
        patch("monitor.deviation.deviation_q.save_alert", new_callable=AsyncMock) as mock_save,
        patch("monitor.deviation.notifier.format_deviation_alert", return_value="msg"),
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock),
    ):
        await _evaluate("005930", "삼성전자", _closes(135.0, ma50=50_000.0))

    args = mock_save.call_args
    code, name, current, ma50, ratio = args.args
    assert code == "005930"
    assert name == "삼성전자"
    assert abs(current - 67_500.0) < 1
    assert abs(ma50 - 50_000.0) < 1
    assert abs(ratio - 135.0) < 0.01
