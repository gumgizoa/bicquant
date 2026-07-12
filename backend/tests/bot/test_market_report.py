"""Tests for the 시장 요약 리포트 (지수 이격도 + ADR + 시장 신용공여 잔고) — bot.

Pure formatting and ADR/이격도 math run offline. Live (``slow``) tests hit the real
LS API (index/ADR) and KOFIA FreeSIS (신용공여 잔고 — 인증이 없어 게이트 픽스처가 없다).
"""

import datetime

import pytest
from bot.features.market_report import (
    adr_from_rows,
    deviation_ratio,
    format_adr_summary,
    format_credit_balance,
    format_deviation_summary,
    format_market_report,
)

from kofiaapi import CreditBalance

# NOTE: bot.main is imported lazily inside the live tests — importing it
# initialises the Azure LLM / Telegram config, which the offline tests must not
# require.

_KOSPI_INDEX = {"code": "001", "name": "코스피", "current": 3300.0, "ma50": 3000.0, "ratio": 110.0}

# 2026-07-09 / 07-08 실제 KOFIA 값 (원 단위)
_CREDIT = CreditBalance(
    date=datetime.date(2026, 7, 9),
    margin_loan=36_633_640_504_452,
    margin_loan_kospi=28_837_404_979_561,
    margin_loan_kosdaq=7_796_235_524_891,
    stock_loan=27_897_150_881,
    stock_loan_kospi=23_808_057_269,
    stock_loan_kosdaq=4_089_093_612,
    subscription_loan=0,
    collateral_loan=25_223_393_125_547,
)
_CREDIT_PREV = CreditBalance(
    date=datetime.date(2026, 7, 8),
    margin_loan=37_199_867_000_000,
    margin_loan_kospi=29_239_165_000_000,
    margin_loan_kosdaq=7_960_702_000_000,
    stock_loan=30_962_000_000,
    stock_loan_kospi=27_544_000_000,
    stock_loan_kosdaq=3_418_000_000,
    subscription_loan=0,
    collateral_loan=24_705_070_000_000,
)


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


def _report(index_entries, adr_entries, credit=None, label=None):
    return format_market_report(
        index_entries,
        adr_entries,
        dev_threshold=130.0,
        adr_overbought=120.0,
        adr_oversold=75.0,
        credit=credit,
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


def test_format_market_report_appends_credit_section_when_given() -> None:
    msg = _report([_KOSPI_INDEX], [], credit=(_CREDIT, _CREDIT_PREV), label="장 마감")
    assert "시장 신용공여 잔고" in msg
    # 이격도 → 신용공여 순서
    assert msg.index("이격도 일일 요약") < msg.index("시장 신용공여 잔고")


def test_format_market_report_omits_credit_when_none() -> None:
    assert "신용공여" not in _report([_KOSPI_INDEX], [], label="장 시작")


# ---------------------------------------------------------------------------
# format_credit_balance — pure function
# ---------------------------------------------------------------------------


def test_format_credit_balance_shows_data_date_not_request_date() -> None:
    assert "시장 신용공여 잔고 (2026-07-09 기준)" in format_credit_balance(_CREDIT)


def test_format_credit_balance_abbreviates_won_amounts() -> None:
    msg = format_credit_balance(_CREDIT)
    assert "융자 36.63조" in msg  # 36_633_640_504_452원
    assert "코스피 28.84조 · 코스닥 7.80조" in msg
    assert "대주 279억" in msg  # 27_897_150_881원


def test_format_credit_balance_shows_day_over_day_delta() -> None:
    msg = format_credit_balance(_CREDIT, _CREDIT_PREV)
    # 융자: 36.63조 - 37.20조 = -5,662억 (-1.52%)
    assert "▼ 5,662억" in msg
    assert "-1.52%" in msg


def test_format_credit_balance_without_previous_row_has_no_delta() -> None:
    msg = format_credit_balance(_CREDIT, None)
    assert "▼" not in msg
    assert "▲" not in msg
    assert "36.63조" in msg


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
async def test_fetch_market_credit_live() -> None:
    """KOFIA는 인증이 없어 게이트 픽스처가 필요 없다. 최신/직전 영업일 쌍을 받아온다."""
    from bot import main as bot_main

    credit = await bot_main._fetch_market_credit()
    assert credit is not None
    latest, previous = credit
    assert previous is not None, "직전 영업일 행도 있어야 전일 대비를 보여줄 수 있다"
    assert latest.date > previous.date
    assert latest.margin_loan == latest.margin_loan_kospi + latest.margin_loan_kosdaq
    assert latest.margin_loan > 0


@pytest.mark.slow
async def test_send_market_report_live(ls_client, telegram) -> None:
    """End-to-end: 실제 LS + KOFIA 데이터로 시장 요약을 만들어 dev 챗으로 발송."""
    from bot import main as bot_main
    from telegram import Bot

    bot = Bot(token=bot_main._cfg.telegram.bot_token)
    async with bot:
        await bot_main._send_market_report(bot, label="테스트 요약", include_credit=True)
