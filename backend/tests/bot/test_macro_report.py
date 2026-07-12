"""Tests for the 해외 거시 지표 리포트 (미 국채 10년물 + 미국 M2) — bot.

Pure formatting runs offline. Live (``slow``) tests hit the real FRED API — 키가 없으면
``fred`` 픽스처가 스킵한다.
"""

import datetime

import pytest
from bot.features.macro_report import MacroPoint, format_m2, format_macro_report, format_treasury_yield

# NOTE: bot.main is imported lazily inside the live tests — importing it
# initialises the Azure LLM / Telegram config, which the offline tests must not
# require.

# 2026-07-09 / 07-08 실제 FRED DGS10 값 (%)
_TREASURY = MacroPoint(date=datetime.date(2026, 7, 9), value=4.54, prev=4.56)

# 2026-05 실제 FRED M2SL 값 (십억 달러). prev=전월(04), year_ago=1년 전(2025-05)
_M2_US = MacroPoint(date=datetime.date(2026, 5, 1), value=23_052.3, prev=22_804.5, year_ago=21_900.0)


# ---------------------------------------------------------------------------
# format_treasury_yield — pure function
# ---------------------------------------------------------------------------


def test_format_treasury_yield_shows_value_and_data_date() -> None:
    msg = format_treasury_yield(_TREASURY, move_alert=0.10)
    assert "<b>4.54%</b>" in msg
    assert "2026-07-09 기준" in msg


def test_format_treasury_yield_shows_day_over_day_move_in_pp() -> None:
    # 4.54 - 4.56 = -0.02%p
    assert "▼ 0.02%p" in format_treasury_yield(_TREASURY, move_alert=0.10)


def test_format_treasury_yield_highlights_move_at_or_above_alert() -> None:
    point = MacroPoint(date=datetime.date(2026, 7, 9), value=4.66, prev=4.56)  # +0.10%p
    assert "⚠️" in format_treasury_yield(point, move_alert=0.10)


def test_format_treasury_yield_no_highlight_below_alert() -> None:
    msg = format_treasury_yield(_TREASURY, move_alert=0.10)  # -0.02%p
    assert "⚠️" not in msg
    assert "🇺🇸" in msg


def test_format_treasury_yield_without_previous_has_no_move() -> None:
    point = MacroPoint(date=datetime.date(2026, 7, 9), value=4.54)
    msg = format_treasury_yield(point, move_alert=0.10)
    assert "%p" not in msg
    assert "4.54%" in msg


# ---------------------------------------------------------------------------
# format_m2 — pure function
# ---------------------------------------------------------------------------


def test_format_m2_abbreviates_to_trillions_and_shows_month() -> None:
    msg = format_m2("미국", _M2_US)
    assert "23.05조 달러" in msg  # 23,052.3 십억 달러
    assert "2026-05 기준" in msg
    assert "2026-05-01" not in msg  # 월별 지표라 일자까지 보여주지 않는다


def test_format_m2_shows_mom_and_yoy() -> None:
    msg = format_m2("미국", _M2_US)
    assert "▲ 1.09% MoM" in msg  # (23052.3 - 22804.5) / 22804.5
    assert "▲ 5.26% YoY" in msg  # (23052.3 - 21900.0) / 21900.0


def test_format_m2_omits_changes_without_history() -> None:
    msg = format_m2("미국", MacroPoint(date=datetime.date(2026, 5, 1), value=23_052.3))
    assert "MoM" not in msg
    assert "YoY" not in msg
    assert "(2026-05 기준)" in msg


def test_format_m2_shows_mom_only_when_year_ago_missing() -> None:
    msg = format_m2("미국", MacroPoint(date=datetime.date(2026, 5, 1), value=23_052.3, prev=22_804.5))
    assert "MoM" in msg
    assert "YoY" not in msg


# ---------------------------------------------------------------------------
# format_macro_report — 두 지표를 한 메시지로
# ---------------------------------------------------------------------------


def _report(treasury, m2_us, label=None):
    return format_macro_report(treasury, m2_us, treasury_move_alert=0.10, label=label)


def test_format_macro_report_combines_both_sections() -> None:
    msg = _report(_TREASURY, _M2_US, label="장 마감")
    assert "해외 거시 지표 (장 마감)" in msg
    assert "미 국채 10년물" in msg
    assert "미국 M2" in msg
    # 금리 → M2 순서
    assert msg.index("미 국채 10년물") < msg.index("미국 M2")


def test_format_macro_report_label_is_optional() -> None:
    assert "(" not in _report(_TREASURY, _M2_US).splitlines()[0]


def test_format_macro_report_omits_missing_indicator() -> None:
    msg = _report(_TREASURY, None)
    assert "미 국채 10년물" in msg
    assert "M2" not in msg


def test_format_macro_report_returns_none_without_data() -> None:
    assert _report(None, None) is None


# ---------------------------------------------------------------------------
# Live: FRED fetchers
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_fetch_treasury_point_live(fred) -> None:
    """DGS10 — 일별이라 직전 거래일 값이 있어야 하고, YoY는 쓰지 않는다."""
    from bot import main as bot_main

    point = await bot_main._fetch_macro_point(bot_main._cfg.macro.treasury_series, monthly=False)
    assert point is not None
    assert 0 < point.value < 25, f"10Y 금리가 %단위 값이어야 한다: {point.value}"
    assert point.prev is not None, "직전 거래일 값이 있어야 전일 대비를 보여줄 수 있다"
    assert point.year_ago is None


@pytest.mark.slow
async def test_fetch_m2_point_live(fred) -> None:
    """M2SL — 월별. MoM/YoY를 보여주려면 전월 + 12개월 전 값이 필요하다."""
    from bot import main as bot_main

    point = await bot_main._fetch_macro_point(bot_main._cfg.macro.m2_us_series, monthly=True)
    assert point is not None
    assert point.value > 10_000, f"M2SL은 십억 달러 단위 (>10조 달러): {point.value}"
    assert point.prev is not None
    assert point.year_ago is not None


@pytest.mark.slow
async def test_fetch_macro_point_returns_none_on_bad_series(fred) -> None:
    """존재하지 않는 계열이면 예외 대신 None — 다른 지표는 계속 나가야 한다."""
    from bot import main as bot_main

    assert await bot_main._fetch_macro_point("NO_SUCH_SERIES_XYZ", monthly=False) is None


@pytest.mark.slow
async def test_send_macro_report_live(fred, telegram) -> None:
    """End-to-end: 실제 FRED 데이터로 거시 지표 리포트를 만들어 dev 챗으로 발송."""
    from bot import main as bot_main
    from telegram import Bot

    bot = Bot(token=bot_main._cfg.telegram.bot_token)
    async with bot:
        await bot_main._send_macro_report(bot, label="테스트 거시")
