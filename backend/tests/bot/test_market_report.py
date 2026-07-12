"""Tests for the 시장 요약 리포트 (지수 이격도 + ADR) — bot.

Pure formatting and ADR math run offline. Live (``slow``) tests hit the real LS
API to verify the index/ADR fetchers.
"""

import pytest
from bot.features.market_report import (
    adr_from_rows,
    deviation_ratio,
    format_adr_summary,
    format_deviation_summary,
    format_market_report,
)

# NOTE: bot.main is imported lazily inside the live tests — importing it
# initialises the Azure LLM / Telegram config, which the offline tests must not
# require.

_KOSPI_INDEX = {"code": "001", "name": "코스피", "current": 3300.0, "ma50": 3000.0, "ratio": 110.0}


# ---------------------------------------------------------------------------
# format_deviation_summary — pure function
# ---------------------------------------------------------------------------


def test_format_deviation_summary_contains_header() -> None:
    assert "이격도 일일 요약" in format_deviation_summary([], threshold=130.0)


def test_format_deviation_summary_highlights_entry_at_or_above_threshold() -> None:
    entries = [{"code": "001", "name": "코스피", "current": 130.0, "ma50": 100.0, "ratio": 130.0}]
    msg = format_deviation_summary(entries, threshold=130.0)
    assert "⚠️" in msg
    assert "<b>130.0</b>" in msg
    assert "코스피" in msg


def test_format_deviation_summary_no_highlight_below_threshold() -> None:
    msg = format_deviation_summary([_KOSPI_INDEX], threshold=130.0)
    assert "⚠️" not in msg
    assert "110.0" in msg


def test_format_deviation_summary_label_is_optional() -> None:
    assert "(장 시작)" in format_deviation_summary([], threshold=130.0, label="장 시작")
    assert "(" not in format_deviation_summary([], threshold=130.0).splitlines()[0]


# ---------------------------------------------------------------------------
# format_adr_summary — pure function
# ---------------------------------------------------------------------------


def test_format_adr_summary_flags_overbought() -> None:
    msg = format_adr_summary([{"code": "001", "name": "코스피", "adr": 125.0}], overbought=120.0, oversold=75.0)
    assert "⚠️" in msg
    assert "과열" in msg
    assert "<b>125.0</b>" in msg


def test_format_adr_summary_flags_oversold() -> None:
    msg = format_adr_summary([{"code": "301", "name": "코스닥", "adr": 70.0}], overbought=120.0, oversold=75.0)
    assert "🔻" in msg
    assert "바닥" in msg


def test_format_adr_summary_neutral_not_flagged() -> None:
    msg = format_adr_summary([{"code": "001", "name": "코스피", "adr": 100.0}], overbought=120.0, oversold=75.0)
    assert "⚠️" not in msg
    assert "🔻" not in msg
    assert "100.0" in msg


# ---------------------------------------------------------------------------
# format_market_report — 이격도 + ADR 를 한 메시지로
# ---------------------------------------------------------------------------


def _report(index_entries, adr_entries, label=None):
    return format_market_report(
        index_entries,
        adr_entries,
        dev_threshold=130.0,
        adr_overbought=120.0,
        adr_oversold=75.0,
        label=label,
    )


def test_format_market_report_combines_both_sections() -> None:
    msg = _report([_KOSPI_INDEX], [{"code": "001", "name": "코스피", "adr": 100.0}], label="장 마감")
    assert "이격도 일일 요약 (장 마감)" in msg
    assert "ADR 일일 요약 (장 마감)" in msg


def test_format_market_report_omits_missing_section() -> None:
    msg = _report([_KOSPI_INDEX], [])
    assert "이격도 일일 요약" in msg
    assert "ADR" not in msg


def test_format_market_report_returns_none_without_data() -> None:
    assert _report([], []) is None


# ---------------------------------------------------------------------------
# adr_from_rows / deviation_ratio — pure math
# ---------------------------------------------------------------------------


def test_adr_from_rows_computes_ratio() -> None:
    # advances: 60+40=100, declines: 30+20=50 -> ADR = 100 * 100/50 = 200
    rows = [
        {"date": "20260101", "high": "60", "low": "30"},
        {"date": "20260102", "high": "40", "low": "20"},
    ]
    assert adr_from_rows(rows, period=20) == pytest.approx(200.0)


def test_adr_from_rows_takes_most_recent_period() -> None:
    # oldest row (advances=999) must be dropped when period=2
    rows = [
        {"date": "20251230", "high": "999", "low": "1"},
        {"date": "20260101", "high": "60", "low": "30"},
        {"date": "20260102", "high": "40", "low": "20"},
    ]
    assert adr_from_rows(rows, period=2) == pytest.approx(200.0)


def test_adr_from_rows_returns_none_when_no_declines() -> None:
    assert adr_from_rows([{"date": "20260101", "high": "10", "low": "0"}], period=20) is None


def test_adr_from_rows_returns_none_when_empty() -> None:
    assert adr_from_rows([], period=20) is None


def test_deviation_ratio_uses_ma50_excluding_latest_close() -> None:
    # 50 bars at 100 (the MA50 window) + latest close 130 -> ratio = 130.0
    closes = [100.0] * 50 + [130.0]
    assert deviation_ratio(closes) == pytest.approx(130.0)


def test_deviation_ratio_needs_51_closes() -> None:
    assert deviation_ratio([100.0] * 50) is None


# ---------------------------------------------------------------------------
# Live: LS API fetchers
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("upcode", ["001", "301"])
async def test_fetch_index_closes_live(ls_client, upcode: str) -> None:
    from bot import main as bot_main

    closes = await bot_main._fetch_index_closes(upcode)
    assert len(closes) >= 51, f"need >=51 bars to compute MA50, got {len(closes)}"
    assert all(c > 0 for c in closes)


@pytest.mark.slow
@pytest.mark.parametrize("upcode", ["001", "301"])
async def test_fetch_adr_live(ls_client, upcode: str) -> None:
    from bot import main as bot_main

    adr = await bot_main._fetch_adr(upcode, period=20)
    assert adr is not None and adr > 0


@pytest.mark.slow
async def test_build_market_entries_live(ls_client) -> None:
    from bot import main as bot_main

    index_entries, adr_entries = await bot_main._build_market_entries()
    assert {e["code"] for e in index_entries} == {"001", "301"}
    assert all(e["ratio"] > 0 for e in index_entries)
    assert all(e["adr"] > 0 for e in adr_entries)


@pytest.mark.slow
async def test_send_market_report_live(ls_client, telegram) -> None:
    """End-to-end: 실제 LS 데이터로 시장 요약을 만들어 dev 챗으로 발송."""
    from bot import main as bot_main
    from telegram import Bot

    bot = Bot(token=bot_main._cfg.telegram.bot_token)
    async with bot:
        await bot_main._send_market_report(bot, label="테스트 요약")
