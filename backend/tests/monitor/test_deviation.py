"""Unit tests for monitor.deviation — _evaluate, _run_eod_summary, and format_deviation_summary."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from monitor.deviation import _evaluate, _run_eod_summary, monitor_deviation
from monitor.notifier import format_deviation_summary


def _closes(ratio: float, ma50: float = 100.0) -> list[float]:
    """Build a closes list where MA50 == ma50 and current/MA50*100 == ratio."""
    return [ma50] * 50 + [ma50 * ratio / 100]


# ---------------------------------------------------------------------------
# _evaluate — alert logic
# ---------------------------------------------------------------------------


async def test_evaluate_fires_alert_above_threshold() -> None:
    with (
        patch("monitor.deviation.deviation_q.save_alert", new_callable=AsyncMock) as mock_save,
        patch("monitor.deviation.notifier.format_deviation_alert", return_value="msg"),
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        await _evaluate("001", "코스피", _closes(131.0))

    mock_save.assert_awaited_once()
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
    with (
        patch("monitor.deviation.deviation_q.save_alert", new_callable=AsyncMock) as mock_save,
        patch("monitor.deviation.notifier.format_deviation_alert", return_value="msg"),
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock),
    ):
        await _evaluate("005930", "삼성전자", _closes(135.0, ma50=50_000.0))

    code, name, current, ma50, ratio = mock_save.call_args.args
    assert code == "005930"
    assert name == "삼성전자"
    assert abs(current - 67_500.0) < 1
    assert abs(ma50 - 50_000.0) < 1
    assert abs(ratio - 135.0) < 0.01


# ---------------------------------------------------------------------------
# _run_eod_summary
# ---------------------------------------------------------------------------


async def test_run_eod_summary_sends_telegram_with_all_entries() -> None:
    closes = _closes(105.0)  # 51 points, ratio=105.0
    mock_client = AsyncMock()

    with (
        patch("monitor.deviation._fetch_index_closes", new_callable=AsyncMock, return_value=closes),
        patch("monitor.deviation._fetch_stock_closes", new_callable=AsyncMock, return_value=closes),
        patch("monitor.deviation._fetch_stock_name", new_callable=AsyncMock, return_value="삼성전자"),
        patch("monitor.deviation.watchlist_q.get_active_codes", new_callable=AsyncMock, return_value=["005930"]),
        patch("monitor.deviation.notifier.format_deviation_summary", return_value="summary") as mock_fmt,
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        await _run_eod_summary(mock_client)

    mock_fmt.assert_called_once()
    entries_arg = mock_fmt.call_args.args[0]
    # 2 indices (_INDICES has 2 items) + 1 watchlist stock
    assert len(entries_arg) == 3
    assert all(abs(e["ratio"] - 105.0) < 0.01 for e in entries_arg)
    mock_send.assert_awaited_once_with("summary")


async def test_run_eod_summary_skips_entries_with_insufficient_data() -> None:
    short_closes = [100.0] * 50  # 50 points — need 51
    mock_client = AsyncMock()

    with (
        patch("monitor.deviation._fetch_index_closes", new_callable=AsyncMock, return_value=short_closes),
        patch("monitor.deviation._fetch_stock_closes", new_callable=AsyncMock, return_value=short_closes),
        patch("monitor.deviation._fetch_stock_name", new_callable=AsyncMock, return_value="삼성전자"),
        patch("monitor.deviation.watchlist_q.get_active_codes", new_callable=AsyncMock, return_value=["005930"]),
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        await _run_eod_summary(mock_client)

    mock_send.assert_not_called()


async def test_run_eod_summary_sends_nothing_when_watchlist_empty_and_indices_short() -> None:
    mock_client = AsyncMock()

    with (
        patch("monitor.deviation._fetch_index_closes", new_callable=AsyncMock, return_value=[]),
        patch("monitor.deviation.watchlist_q.get_active_codes", new_callable=AsyncMock, return_value=[]),
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        await _run_eod_summary(mock_client)

    mock_send.assert_not_called()


async def test_run_eod_summary_entry_ratio_correct() -> None:
    """Verify the computed ratio in the entry matches expected value."""
    closes = _closes(140.0, ma50=50_000.0)
    mock_client = AsyncMock()

    with (
        patch("monitor.deviation._fetch_index_closes", new_callable=AsyncMock, return_value=closes),
        patch("monitor.deviation._fetch_stock_closes", new_callable=AsyncMock, return_value=[]),
        patch("monitor.deviation.watchlist_q.get_active_codes", new_callable=AsyncMock, return_value=[]),
        patch("monitor.deviation.notifier.format_deviation_summary", return_value="msg") as mock_fmt,
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock),
    ):
        await _run_eod_summary(mock_client)

    entries = mock_fmt.call_args.args[0]
    index_entry = next(e for e in entries if e["code"] == "001")
    assert abs(index_entry["ratio"] - 140.0) < 0.01
    assert abs(index_entry["current"] - 70_000.0) < 1
    assert abs(index_entry["ma50"] - 50_000.0) < 1


async def test_run_eod_summary_passes_default_label_to_formatter() -> None:
    """Default call must forward label='장 마감' to format_deviation_summary."""
    closes = _closes(105.0)
    mock_client = AsyncMock()

    with (
        patch("monitor.deviation._fetch_index_closes", new_callable=AsyncMock, return_value=closes),
        patch("monitor.deviation._fetch_stock_closes", new_callable=AsyncMock, return_value=[]),
        patch("monitor.deviation.watchlist_q.get_active_codes", new_callable=AsyncMock, return_value=[]),
        patch("monitor.deviation.notifier.format_deviation_summary", return_value="msg") as mock_fmt,
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock),
    ):
        await _run_eod_summary(mock_client)

    assert mock_fmt.call_args.kwargs["label"] == "장 마감"


async def test_run_eod_summary_passes_custom_label_to_formatter() -> None:
    """Call with label='장 시작' must propagate to format_deviation_summary."""
    closes = _closes(105.0)
    mock_client = AsyncMock()

    with (
        patch("monitor.deviation._fetch_index_closes", new_callable=AsyncMock, return_value=closes),
        patch("monitor.deviation._fetch_stock_closes", new_callable=AsyncMock, return_value=[]),
        patch("monitor.deviation.watchlist_q.get_active_codes", new_callable=AsyncMock, return_value=[]),
        patch("monitor.deviation.notifier.format_deviation_summary", return_value="msg") as mock_fmt,
        patch("monitor.deviation.notifier.send_telegram", new_callable=AsyncMock),
    ):
        await _run_eod_summary(mock_client, label="장 시작")

    assert mock_fmt.call_args.kwargs["label"] == "장 시작"


# ---------------------------------------------------------------------------
# monitor_deviation — morning summary loop behavior
# ---------------------------------------------------------------------------


async def test_monitor_deviation_morning_summary_fires_once_at_open() -> None:
    """Morning summary runs once when market opens; not on subsequent polls."""
    iterations = 0

    def fake_market_hours():
        nonlocal iterations
        iterations += 1
        if iterations <= 3:
            return True
        raise asyncio.CancelledError()

    mock_client = AsyncMock()
    mock_ls_instance = MagicMock()
    mock_ls_instance.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ls_instance.__aexit__ = AsyncMock(return_value=False)

    mock_cfg = MagicMock()
    mock_cfg.ls_api.app_key = "test_key"
    mock_cfg.ls_api.app_secret = "test_secret"

    with (
        patch("monitor.deviation.cfg", mock_cfg),
        patch("monitor.deviation.LSClient", return_value=mock_ls_instance),
        patch("monitor.deviation.is_market_hours", side_effect=fake_market_hours),
        patch("monitor.deviation._run_eod_summary", new_callable=AsyncMock) as mock_summary,
        patch("monitor.deviation._run_poll", new_callable=AsyncMock),
        patch("monitor.deviation.asyncio.sleep", new_callable=AsyncMock),
    ):
        try:
            await monitor_deviation()
        except asyncio.CancelledError:
            pass

    # First call: label="장 시작" (morning); no further summary calls during polling
    assert mock_summary.await_count == 1
    assert mock_summary.call_args.kwargs["label"] == "장 시작"


async def test_monitor_deviation_morning_summary_resets_after_close() -> None:
    """After market closes (EOD summary), morning summary fires again on next open."""
    sequence = [True, False, False, True]
    idx = 0

    def fake_market_hours():
        nonlocal idx
        if idx >= len(sequence):
            raise asyncio.CancelledError()
        val = sequence[idx]
        idx += 1
        return val

    mock_client = AsyncMock()
    mock_ls_instance = MagicMock()
    mock_ls_instance.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ls_instance.__aexit__ = AsyncMock(return_value=False)

    mock_cfg = MagicMock()
    mock_cfg.ls_api.app_key = "test_key"
    mock_cfg.ls_api.app_secret = "test_secret"

    with (
        patch("monitor.deviation.cfg", mock_cfg),
        patch("monitor.deviation.LSClient", return_value=mock_ls_instance),
        patch("monitor.deviation.is_market_hours", side_effect=fake_market_hours),
        patch("monitor.deviation._run_eod_summary", new_callable=AsyncMock) as mock_summary,
        patch("monitor.deviation._run_poll", new_callable=AsyncMock),
        patch("monitor.deviation.seconds_until_market_open", return_value=0.0),
        patch("monitor.deviation.asyncio.sleep", new_callable=AsyncMock),
    ):
        try:
            await monitor_deviation()
        except asyncio.CancelledError:
            pass

    # Calls: "장 시작" on first open, "장 마감" on close, "장 시작" on second open
    assert mock_summary.await_count == 3
    # EOD call uses default (no kwarg), morning calls pass label explicitly
    labels = [c.kwargs.get("label", "장 마감") for c in mock_summary.await_args_list]
    assert labels == ["장 시작", "장 마감", "장 시작"]


# ---------------------------------------------------------------------------
# format_deviation_summary
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
