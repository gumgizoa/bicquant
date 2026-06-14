"""Unit tests for monitor.dart_monitor and DART notifier formatters."""

import asyncio
from unittest.mock import AsyncMock, patch

import pandas as pd
from monitor.dart_monitor import (
    _check_new_disclosures,
    _fetch_disclosures,
    _seen_rcept_nos,
    _send_morning_summary,
    monitor_dart_disclosures,
)
from monitor.notifier import format_dart_daily_count, format_dart_new_disclosure

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# format_dart_daily_count
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
# format_dart_new_disclosure
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
# _send_morning_summary
# ---------------------------------------------------------------------------


async def test_send_morning_summary_initializes_seen_and_sends_count() -> None:
    disclosures = [_disc("D001"), _disc("D002", corp_cls="코")]

    with (
        patch("monitor.dart_monitor._fetch_disclosures", new_callable=AsyncMock, return_value=disclosures),
        patch("monitor.dart_monitor.notifier.format_dart_daily_count", return_value="count_msg") as mock_fmt,
        patch("monitor.dart_monitor.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        _seen_rcept_nos.clear()
        await _send_morning_summary("20260602")

    mock_fmt.assert_called_once_with("20260602", 2, {"유": 1, "코": 1})
    mock_send.assert_awaited_once_with("count_msg")
    assert "D001" in _seen_rcept_nos
    assert "D002" in _seen_rcept_nos


async def test_send_morning_summary_handles_fetch_error_gracefully() -> None:
    with (
        patch("monitor.dart_monitor._fetch_disclosures", new_callable=AsyncMock, side_effect=Exception("net")),
        patch("monitor.dart_monitor.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        await _send_morning_summary("20260602")  # must not raise

    mock_send.assert_not_called()


async def test_send_morning_summary_empty_disclosures() -> None:
    with (
        patch("monitor.dart_monitor._fetch_disclosures", new_callable=AsyncMock, return_value=[]),
        patch("monitor.dart_monitor.notifier.format_dart_daily_count", return_value="msg") as mock_fmt,
        patch("monitor.dart_monitor.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        _seen_rcept_nos.clear()
        await _send_morning_summary("20260602")

    mock_fmt.assert_called_once_with("20260602", 0, {})
    mock_send.assert_awaited_once()


# ---------------------------------------------------------------------------
# _check_new_disclosures
# ---------------------------------------------------------------------------


async def test_check_new_disclosures_notifies_only_new() -> None:
    disclosures = [_disc("N001"), _disc("N002")]

    with (
        patch("monitor.dart_monitor._fetch_disclosures", new_callable=AsyncMock, return_value=disclosures),
        patch("monitor.dart_monitor.notifier.format_dart_new_disclosure", return_value="new_msg"),
        patch("monitor.dart_monitor.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        _seen_rcept_nos.clear()
        _seen_rcept_nos.add("N001")  # already seen
        await _check_new_disclosures("20260602")

    mock_send.assert_awaited_once()  # only N002 is new


async def test_check_new_disclosures_skips_all_if_already_seen() -> None:
    disclosures = [_disc("N001"), _disc("N002")]

    with (
        patch("monitor.dart_monitor._fetch_disclosures", new_callable=AsyncMock, return_value=disclosures),
        patch("monitor.dart_monitor.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        _seen_rcept_nos.clear()
        _seen_rcept_nos.update(["N001", "N002"])
        await _check_new_disclosures("20260602")

    mock_send.assert_not_called()


async def test_check_new_disclosures_adds_new_to_seen() -> None:
    disclosures = [_disc("N003")]

    with (
        patch("monitor.dart_monitor._fetch_disclosures", new_callable=AsyncMock, return_value=disclosures),
        patch("monitor.dart_monitor.notifier.format_dart_new_disclosure", return_value="msg"),
        patch("monitor.dart_monitor.notifier.send_telegram", new_callable=AsyncMock),
    ):
        _seen_rcept_nos.clear()
        await _check_new_disclosures("20260602")

    assert "N003" in _seen_rcept_nos


async def test_check_new_disclosures_handles_fetch_error_gracefully() -> None:
    with (
        patch("monitor.dart_monitor._fetch_disclosures", new_callable=AsyncMock, side_effect=Exception("timeout")),
        patch("monitor.dart_monitor.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        await _check_new_disclosures("20260602")  # must not raise

    mock_send.assert_not_called()


async def test_check_new_disclosures_sends_notification_per_new_item() -> None:
    """Each new disclosure generates its own Telegram message."""
    disclosures = [_disc("M001"), _disc("M002"), _disc("M003")]

    with (
        patch("monitor.dart_monitor._fetch_disclosures", new_callable=AsyncMock, return_value=disclosures),
        patch("monitor.dart_monitor.notifier.format_dart_new_disclosure", side_effect=lambda d: d["rcept_no"]),
        patch("monitor.dart_monitor.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
    ):
        _seen_rcept_nos.clear()
        await _check_new_disclosures("20260602")

    assert mock_send.await_count == 3
    sent_texts = [call.args[0] for call in mock_send.await_args_list]
    assert sent_texts == ["M001", "M002", "M003"]


# ---------------------------------------------------------------------------
# _fetch_disclosures — listed-company filter
# ---------------------------------------------------------------------------


async def test_fetch_disclosures_keeps_only_listed() -> None:
    """corp_cls '유' and '코' pass; '채', '기', '넥' are excluded."""
    all_records = [
        _disc("F001", corp_cls="유"),
        _disc("F002", corp_cls="코"),
        _disc("F003", corp_cls="채"),
        _disc("F004", corp_cls="기"),
        _disc("F005", corp_cls="넥"),
    ]

    with patch("monitor.dart_monitor.list_dart_disclosures_by_date", return_value=all_records):
        result = await _fetch_disclosures("20260602", 3)

    assert len(result) == 2
    assert {d["corp_cls"] for d in result} == {"유", "코"}


async def test_fetch_disclosures_returns_empty_when_no_listed() -> None:
    all_records = [_disc("F010", corp_cls="채"), _disc("F011", corp_cls="기")]

    with patch("monitor.dart_monitor.list_dart_disclosures_by_date", return_value=all_records):
        result = await _fetch_disclosures("20260602", 1)

    assert result == []


async def test_fetch_disclosures_passes_correct_args() -> None:
    """Verifies date and end_page are forwarded to list_dart_disclosures_by_date."""
    with patch("monitor.dart_monitor.list_dart_disclosures_by_date", return_value=[]) as mock_fn:
        await _fetch_disclosures("20260602", 5)

    mock_fn.assert_called_once_with("20260602", 1, 5)


async def test_fetch_disclosures_keeps_only_monitored_subjects() -> None:
    """Listed companies pass only when report_nm matches a monitored subject."""
    all_records = [
        _disc("S001", report_nm="주요사항보고서(유상증자결정)"),
        _disc("S002", report_nm="주요사항보고서(무상증자결정)"),
        _disc("S003", report_nm="중대재해발생"),
        _disc("S004", report_nm="최대주주변경을수반하는주식양수도계약체결"),
        _disc("S005", report_nm="단일판매ㆍ공급계약체결"),
        _disc("S006", report_nm="매출액또는손익구조30%(대규모법인은15%)이상변동"),
        _disc("S007", report_nm="주식소각결정"),
        _disc("S008", report_nm="신규시설투자등"),
        # Excluded: listed companies but unrelated subjects.
        _disc("S009", report_nm="분기보고서 (2026.03)"),
        _disc("S010", report_nm="투자설명서"),
        _disc("S011", report_nm="최대주주등소유주식변동신고서"),
    ]

    with patch("monitor.dart_monitor.list_dart_disclosures_by_date", return_value=all_records):
        result = await _fetch_disclosures("20260602", 3)

    assert {d["rcept_no"] for d in result} == {f"S00{i}" for i in range(1, 9)}


async def test_fetch_disclosures_excludes_unlisted_even_if_subject_matches() -> None:
    """Subject match alone is not enough; the company must be listed (유/코)."""
    all_records = [
        _disc("S100", corp_cls="채", report_nm="주식소각결정"),
        _disc("S101", corp_cls="유", report_nm="주식소각결정"),
    ]

    with patch("monitor.dart_monitor.list_dart_disclosures_by_date", return_value=all_records):
        result = await _fetch_disclosures("20260602", 1)

    assert {d["rcept_no"] for d in result} == {"S101"}


# ---------------------------------------------------------------------------
# monitor_dart_disclosures — loop behavior
# ---------------------------------------------------------------------------


async def test_monitor_dart_disclosures_morning_fires_once_then_polls() -> None:
    """Morning summary runs once; subsequent iterations call _check_new_disclosures."""
    iterations = 0

    def fake_market_hours():
        nonlocal iterations
        iterations += 1
        if iterations <= 3:
            return True
        raise asyncio.CancelledError()

    with (
        patch("monitor.dart_monitor.is_market_hours", side_effect=fake_market_hours),
        patch("monitor.dart_monitor._send_morning_summary", new_callable=AsyncMock) as mock_morning,
        patch("monitor.dart_monitor._check_new_disclosures", new_callable=AsyncMock) as mock_poll,
        patch("monitor.dart_monitor.asyncio.sleep", new_callable=AsyncMock),
    ):
        _seen_rcept_nos.clear()
        try:
            await monitor_dart_disclosures()
        except asyncio.CancelledError:
            pass

    mock_morning.assert_awaited_once()
    assert mock_poll.await_count == 2  # iterations 2 and 3


async def test_monitor_dart_disclosures_resets_state_after_market_close() -> None:
    """After market closes, morning_sent resets so next open fires summary again."""
    # Sequence: open → close (reset) → open again
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
        patch("monitor.dart_monitor.is_market_hours", side_effect=fake_market_hours),
        patch("monitor.dart_monitor._send_morning_summary", new_callable=AsyncMock) as mock_morning,
        patch("monitor.dart_monitor._check_new_disclosures", new_callable=AsyncMock),
        patch("monitor.dart_monitor.seconds_until_market_open", return_value=0.0),
        patch("monitor.dart_monitor.asyncio.sleep", new_callable=AsyncMock),
    ):
        _seen_rcept_nos.clear()
        try:
            await monitor_dart_disclosures()
        except asyncio.CancelledError:
            pass

    # Morning summary fires on first open AND again after close+reopen
    assert mock_morning.await_count == 2
