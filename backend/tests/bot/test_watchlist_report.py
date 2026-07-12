"""Tests for the 관심종목 리포트 formatter (bot).

Pure formatting tests run offline. Live (``slow``) tests hit the real LS API to
verify the 신용/공매도/대차 fetchers.
"""

import pytest
from bot.features.watchlist_report import format_watchlist_report

# NOTE: bot.main is imported lazily inside the live tests — importing it
# initialises the Azure LLM / Telegram config, which the offline tests must not
# require.

_KR = {
    "code": "005930",
    "name": "삼성전자",
    "is_kr": True,
    "ratio": 106.0,
    "mdd": -21.1,
    "mdd_days": 60,
    "credit": {
        "yjvolume": "24851117",
        "yjprice": "5528805",
        "yjrate": "0.43",
        "ygrate": "7.58",
        "yj5days": "3.47",
        "yj20days": "13.43",
        "djvolume": "11199",
    },
    "short": {"gm_vo": "368578", "gm_va": "109369", "gm_per": "1.17", "gm_vo_sum": "29409464"},
    "lending": {"upvolume": "9044214", "dnvolume": "1642789", "tovolume": "86582650", "tovoldif": "7401425"},
}


def _fmt(entries, **kw):
    kw.setdefault("dev_threshold", 130.0)
    kw.setdefault("mdd_alert", -20.0)
    return format_watchlist_report(entries, **kw)


# ---------------------------------------------------------------------------
# format_watchlist_report — pure function
# ---------------------------------------------------------------------------


def test_empty_watchlist_message() -> None:
    msg = _fmt([])
    assert "관심종목 리포트" in msg
    assert "/watch" in msg


def test_header_uses_label() -> None:
    msg = _fmt([], label="장 시작")
    assert "장 시작" in msg
    assert "장 마감" not in msg


def test_header_has_no_tag_without_label() -> None:
    # /report (수동 조회) — 헤더에 괄호 태그가 붙지 않는다
    msg = _fmt([_KR])
    assert msg.startswith("📋 <b>관심종목 리포트</b>")
    assert "(" not in msg.splitlines()[0]


def test_full_kr_entry_renders_all_sections() -> None:
    msg = _fmt([_KR])
    assert "삼성전자 (005930)" in msg
    assert "이격도" in msg and "106.0" in msg
    assert "MDD" in msg and "-21.1%" in msg and "60 거래일" in msg
    assert "융자 잔고 24,851,117주 / 5,528,805백만원" in msg
    assert "잔고율 0.43% · 공여율 7.58%" in msg
    assert "5일 +3.47% · 20일 +13.43%" in msg
    assert "대주잔고 11,199주" in msg
    assert "공매도 368,578주 / 109,369백만원" in msg
    assert "비중 1.17% · 누적 29,409,464주" in msg
    assert "대차 신규 9,044,214 / 상환 1,642,789" in msg
    assert "잔고 86,582,650주 · 증감 +7,401,425" in msg


def test_credit_sections_omitted_when_absent() -> None:
    # 장 시작 리포트: 이격도/MDD만
    e = {k: v for k, v in _KR.items() if k not in ("credit", "short", "lending")}
    msg = _fmt([e], label="장 시작")
    assert "이격도" in msg
    assert "MDD" in msg
    assert "융자" not in msg
    assert "공매도" not in msg
    assert "대차" not in msg


def test_deviation_flagged_at_or_above_threshold() -> None:
    hot = {**_KR, "ratio": 130.0}
    assert "⚠️" in _fmt([hot])
    cool = {k: v for k, v in _KR.items() if k not in ("mdd",)}
    cool["ratio"] = 106.0
    assert "⚠️" not in _fmt([cool])


def test_mdd_flagged_at_or_below_alert() -> None:
    e = {"code": "005930", "name": "삼성전자", "is_kr": True, "mdd": -20.0, "mdd_days": 60}
    assert "⚠️" in _fmt([e])
    e2 = {**e, "mdd": -19.9}
    assert "⚠️" not in _fmt([e2])


def test_us_entry_shows_mdd_only() -> None:
    us = {"code": "AAPL", "name": "AAPL", "is_kr": False, "mdd": -12.7, "mdd_days": 30}
    msg = _fmt([us])
    assert "AAPL" in msg and "🇺🇸" in msg
    assert "-12.7%" in msg
    assert "융자" not in msg


def test_multiple_entries_all_present() -> None:
    us = {"code": "AAPL", "name": "AAPL", "is_kr": False, "mdd": -12.7, "mdd_days": 30}
    msg = _fmt([_KR, us])
    assert "삼성전자" in msg
    assert "AAPL" in msg


def test_missing_credit_fields_do_not_crash() -> None:
    e = {"code": "005930", "name": "삼성전자", "is_kr": True, "credit": {}, "short": {}, "lending": {}}
    # empty dicts are falsy -> sections skipped, no exception
    msg = _fmt([e])
    assert "삼성전자" in msg


# ---------------------------------------------------------------------------
# Live: 신용/공매도/대차 fetchers (LS API)
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_fetch_credit_info_live(ls_client) -> None:
    from bot.main import _fetch_credit_info

    d = await _fetch_credit_info("005930")
    assert d is not None
    assert float(d["yjvolume"]) > 0  # 융자잔고수량


@pytest.mark.slow
async def test_fetch_short_daily_live(ls_client) -> None:
    from bot.main import _fetch_short_daily

    d = await _fetch_short_daily("005930")
    assert d is not None
    assert "gm_vo" in d and "gm_per" in d


@pytest.mark.slow
async def test_fetch_lending_daily_live(ls_client) -> None:
    from bot.main import _fetch_lending_daily

    d = await _fetch_lending_daily("005930")
    assert d is not None
    assert float(d["tovolume"]) > 0  # 대차잔고
