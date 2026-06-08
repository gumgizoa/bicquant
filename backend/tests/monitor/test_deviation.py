"""Unit tests for monitor.deviation — _evaluate, _run_eod_summary, and format_deviation_summary."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from monitor.deviation import (
    _evaluate,
    _fetch_index_closes,
    _fetch_stock_closes,
    _run_eod_summary,
    monitor_deviation,
)
from monitor.notifier import format_deviation_summary


def _closes(ratio: float, ma50: float = 100.0) -> list[float]:
    """Build a closes list where MA50 == ma50 and current/MA50*100 == ratio."""
    return [ma50] * 50 + [ma50 * ratio / 100]


# ---------------------------------------------------------------------------
# _fetch_index_closes / _fetch_stock_closes — qrycnt must be int (t8419/t8451 spec)
# ---------------------------------------------------------------------------


async def test_fetch_index_closes_sends_qrycnt_as_int() -> None:
    mock_resp = MagicMock()
    mock_resp.block.return_value = [{"close": "100"}]
    mock_client = AsyncMock()
    mock_client.call.return_value = mock_resp

    await _fetch_index_closes(mock_client, "001", count=60)

    body = mock_client.call.call_args.args[1]
    assert isinstance(body["t8419InBlock"]["qrycnt"], int)


async def test_fetch_stock_closes_sends_qrycnt_as_int() -> None:
    mock_resp = MagicMock()
    mock_resp.block.return_value = [{"close": "100"}]
    mock_client = AsyncMock()
    mock_client.call.return_value = mock_resp

    await _fetch_stock_closes(mock_client, "005930", count=60)

    body = mock_client.call.call_args.args[1]
    assert isinstance(body["t8451InBlock"]["qrycnt"], int)


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
# monitor_deviation — startup summary + loop behavior
# ---------------------------------------------------------------------------


def _make_ls_mock() -> tuple[AsyncMock, MagicMock]:
    mock_client = AsyncMock()
    mock_ls_instance = MagicMock()
    mock_ls_instance.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ls_instance.__aexit__ = AsyncMock(return_value=False)
    return mock_client, mock_ls_instance


def _make_cfg_mock() -> MagicMock:
    mock_cfg = MagicMock()
    mock_cfg.ls_api.app_key = "test_key"
    mock_cfg.ls_api.app_secret = "test_secret"
    return mock_cfg


async def test_monitor_deviation_startup_summary_fires_before_loop() -> None:
    """Startup summary always fires once with label='서비스 시작' before any loop logic."""
    # is_market_hours: pre-loop=False, then immediately CancelledError in loop
    call_count = 0

    def fake_market_hours():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return False
        raise asyncio.CancelledError()

    _, mock_ls_instance = _make_ls_mock()

    with (
        patch("monitor.deviation.cfg", _make_cfg_mock()),
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

    assert mock_summary.await_count == 1
    assert mock_summary.call_args.kwargs["label"] == "서비스 시작"


async def test_monitor_deviation_no_duplicate_morning_summary_when_starting_during_market() -> None:
    """When starting during market hours, startup summary serves as the morning message;
    no additional '장 시작' message is sent during that session."""
    # is_market_hours: pre-loop=True, 3 loop iterations, then CancelledError
    iterations = 0

    def fake_market_hours():
        nonlocal iterations
        iterations += 1
        if iterations <= 4:
            return True
        raise asyncio.CancelledError()

    _, mock_ls_instance = _make_ls_mock()

    with (
        patch("monitor.deviation.cfg", _make_cfg_mock()),
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

    # Only the startup summary; no '장 시작' duplicate
    assert mock_summary.await_count == 1
    assert mock_summary.call_args.kwargs["label"] == "서비스 시작"


async def test_monitor_deviation_morning_summary_fires_when_starting_outside_market() -> None:
    """When starting outside market hours, morning summary still fires when market opens."""
    # is_market_hours sequence: pre-loop=False, loop1=False(closed), loop2=True(open), loop3=True, CancelledError
    sequence = [False, False, True, True]
    idx = 0

    def fake_market_hours():
        nonlocal idx
        if idx >= len(sequence):
            raise asyncio.CancelledError()
        val = sequence[idx]
        idx += 1
        return val

    _, mock_ls_instance = _make_ls_mock()

    with (
        patch("monitor.deviation.cfg", _make_cfg_mock()),
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

    assert mock_summary.await_count == 2
    labels = [c.kwargs.get("label", "장 마감") for c in mock_summary.await_args_list]
    assert labels == ["서비스 시작", "장 시작"]


async def test_monitor_deviation_morning_summary_resets_after_close() -> None:
    """After EOD summary, morning summary fires again on the next open."""
    # is_market_hours sequence: pre-loop=True, loop1=False(close), loop2=False, loop3=True(reopen), CancelledError
    sequence = [True, False, False, True]
    idx = 0

    def fake_market_hours():
        nonlocal idx
        if idx >= len(sequence):
            raise asyncio.CancelledError()
        val = sequence[idx]
        idx += 1
        return val

    _, mock_ls_instance = _make_ls_mock()

    with (
        patch("monitor.deviation.cfg", _make_cfg_mock()),
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

    # Calls in order: "서비스 시작" (startup), "장 마감" (EOD), "장 시작" (next morning)
    assert mock_summary.await_count == 3
    labels = [c.kwargs.get("label", "장 마감") for c in mock_summary.await_args_list]
    assert labels == ["서비스 시작", "장 마감", "장 시작"]


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
