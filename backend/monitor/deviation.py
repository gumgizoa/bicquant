"""Deviation ratio + ADR monitor — reports at market open and close.

Deviation ratio = (current price / 50-day moving average) x 100.
ADR (advance-decline ratio) = 100 x (sum of advancing issues) /
(sum of declining issues) over the last ``adr.period`` trading days, per market
index. MDD (maximum drawdown) over the last ``mdd.period`` trading days is
reported per watchlist stock. A single combined summary (이격도 + ADR + MDD) is
sent at session start (장 시작) and session end (장 마감). Deviation entries alert
individually when ratio >= deviation.threshold (default 130); MDD entries are
flagged when at or below ``mdd.alert_threshold``.
"""

import asyncio
import logging

import numpy as np
from shared.config import get_config
from shared.queries import watchlist as watchlist_q

from lsapi import AsyncLSClient as LSClient
from monitor import notifier
from monitor.market_hours import is_market_hours, seconds_until_market_close, seconds_until_market_open

log = logging.getLogger(__name__)

cfg = get_config("monitor")


# KOSPI=001, KOSDAQ=301
_INDICES = [
    ("001", "코스피"),
    ("301", "코스닥"),
]

# Stock names don't change; cache them to avoid redundant t1101 calls.
_stock_name_cache: dict[str, str] = {}


async def _fetch_index_closes(client: LSClient, upcode: str, count: int = 60) -> list[float]:
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            resp = await client.call(
                "t8429",
                {
                    "t8429InBlock": {
                        "shcode": upcode,
                        "gubun": "2",  # daily bars (spec: 2=일, 3=주, 4=월)
                        "qrycnt": count,
                        "sdate": "",
                        "edate": "99999999",
                        "cts_date": "",
                        "comp_yn": "N",
                    }
                },
            )
            return [float(r["close"]) for r in (resp.block("t8429OutBlock1") or []) if r.get("close")]
        except Exception as e:
            last_exc = e
            if attempt == 0 and "IGW00201" in str(e):
                log.warning("t8419 rate-limited for %s (IGW00201); retrying in 3s", upcode)
                await asyncio.sleep(3)
            else:
                raise
    raise last_exc  # type: ignore[misc]


async def _fetch_stock_closes(client: LSClient, shcode: str, count: int = 60) -> list[float]:
    resp = await client.call(
        "t8451",
        {
            "t8451InBlock": {
                "shcode": shcode,
                "gubun": "2",  # daily bars (spec: 2=일, 3=주, 4=월, 5=년)
                "qrycnt": count,
                "sdate": "",
                "edate": "99999999",
                "cts_date": "",
                "comp_yn": "N",
                "sujung": "1",  # adjusted price
                "exchgubun": "K",
            }
        },
    )
    return [float(r["close"]) for r in (resp.block("t8451OutBlock1") or []) if r.get("close")]


async def _fetch_stock_name(client: LSClient, shcode: str) -> str:
    if shcode in _stock_name_cache:
        return _stock_name_cache[shcode]
    try:
        resp = await client.call("t1101", shcode=shcode)
        name = (resp.block("t1101OutBlock") or {}).get("hname", shcode)
        _stock_name_cache[shcode] = name
        return name
    except Exception:
        return shcode


async def _fetch_adr(client: LSClient, upcode: str, period: int) -> float | None:
    """Advance-decline ratio (ADR) for a market index via t1514 (업종기간별추이).

    ADR = 100 * sum(advancing issues) / sum(declining issues) over the most
    recent ``period`` daily bars. Returns ``None`` when data is unavailable or
    the declining-issue sum is zero (avoids divide-by-zero).
    """
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            resp = await client.call(
                "t1514",
                {
                    "t1514InBlock": {
                        "upcode": upcode,
                        "gubun1": "",  # unused per spec
                        "gubun2": "1",  # daily bars (spec: 1=일, 2=주, 3=월)
                        "cts_date": "",
                        "cnt": period,
                        "rate_gbn": "",
                    }
                },
            )
            rows = resp.block("t1514OutBlock1") or []
            rows = sorted(rows, key=lambda r: r.get("date", ""))[-period:]
            up_sum = sum(int(float(r["high"])) for r in rows if str(r.get("high", "")).strip())
            down_sum = sum(int(float(r["low"])) for r in rows if str(r.get("low", "")).strip())
            if down_sum == 0:
                return None
            return 100.0 * up_sum / down_sum
        except Exception as e:
            last_exc = e
            if attempt == 0 and "IGW00201" in str(e):
                log.warning("t1514 rate-limited for %s (IGW00201); retrying in 3s", upcode)
                await asyncio.sleep(3)
            else:
                raise
    raise last_exc  # type: ignore[misc]


def _max_drawdown_pct(closes: list[float]) -> float:
    """Maximum drawdown (%) over a chronological close series (non-positive).

    Drawdown at each point is (price - running_peak) / running_peak; MDD is the
    most negative such value. ``closes`` must be oldest-first. Returns 0.0 for an
    empty series or one that never falls below its running peak.
    """
    peak = 0.0
    mdd = 0.0
    for price in closes:
        if price > peak:
            peak = price
        if peak > 0:
            dd = (price - peak) / peak * 100.0
            if dd < mdd:
                mdd = dd
    return mdd


async def _run_summary(client: LSClient, label: str = "장 마감") -> None:
    """Compute indicators and send two Telegram messages.

    Message 1 (시장): index deviation ratio + ADR.
    Message 2 (관심종목): watchlist deviation ratio + MDD.
    """
    log.info("Running deviation summary (%s).", label)

    # ---- Market indices: deviation ratio + ADR ----
    index_entries = []
    for upcode, name in _INDICES:
        closes = await _fetch_index_closes(client, upcode)
        if len(closes) >= 51:
            current = closes[-1]
            ma50 = float(np.mean(closes[-51:-1]))
            if ma50 > 0:
                index_entries.append({"code": upcode, "name": name, "current": current, "ma50": ma50, "ratio": current / ma50 * 100})

    adr_entries = []
    for upcode, name in _INDICES:
        adr = await _fetch_adr(client, upcode, cfg.adr.period)
        if adr is not None:
            adr_entries.append({"code": upcode, "name": name, "adr": adr})

    # ---- Watchlist stocks: deviation ratio + MDD (over cfg.mdd.period) ----
    # Fetch enough bars for both (MA50 needs >=51, MDD needs cfg.mdd.period).
    mdd_period = cfg.mdd.period
    stock_entries = []
    mdd_entries = []
    for shcode in await watchlist_q.get_active_codes():
        name = await _fetch_stock_name(client, shcode)
        closes = await _fetch_stock_closes(client, shcode, count=max(60, mdd_period))
        if len(closes) >= 51:
            current = closes[-1]
            ma50 = float(np.mean(closes[-51:-1]))
            if ma50 > 0:
                stock_entries.append({"code": shcode, "name": name, "current": current, "ma50": ma50, "ratio": current / ma50 * 100})
        if len(closes) >= 2:
            mdd_entries.append({"code": shcode, "name": name, "mdd": _max_drawdown_pct(closes[-mdd_period:])})

    # ---- Message 1: 시장 (index deviation + ADR) ----
    market_parts = []
    if index_entries:
        market_parts.append(notifier.format_deviation_summary(index_entries, cfg.deviation.threshold, label=label))
    if adr_entries:
        market_parts.append(notifier.format_adr_summary(adr_entries, cfg.adr.overbought, cfg.adr.oversold, label=label))
    if market_parts:
        await notifier.send_telegram("\n\n".join(market_parts))
    else:
        log.warning("Market summary (%s): no data available.", label)

    # ---- Message 2: 관심종목 (watchlist deviation + MDD) ----
    watchlist_parts = []
    if stock_entries:
        watchlist_parts.append(notifier.format_deviation_summary(stock_entries, cfg.deviation.threshold, label=label))
    if mdd_entries:
        watchlist_parts.append(notifier.format_mdd_summary(mdd_entries, cfg.mdd.alert_threshold, mdd_period, label=label))
    if watchlist_parts:
        await notifier.send_telegram("\n\n".join(watchlist_parts))


async def monitor_deviation() -> None:
    async with LSClient(cfg.ls_api.app_key, cfg.ls_api.app_secret) as client:
        try:
            await _run_summary(client, label="서비스 시작")
        except Exception as e:
            log.error("Startup summary error: %s", e)
            await notifier.notify_service_error("Deviation startup summary", e)

        session_active = is_market_hours()
        morning_summary_sent = session_active
        while True:
            if not is_market_hours():
                if session_active:
                    session_active = False
                    morning_summary_sent = False
                    try:
                        await _run_summary(client)
                    except Exception as e:
                        log.error("EOD summary error: %s", e)
                        await notifier.notify_service_error("Deviation EOD summary", e)

                wait = seconds_until_market_open()
                log.info("Market closed. Waiting %.0fs until next open.", wait)
                await asyncio.sleep(wait)
                continue

            session_active = True

            if not morning_summary_sent:
                try:
                    await _run_summary(client, label="장 시작")
                except Exception as e:
                    log.error("Morning summary error: %s", e)
                    await notifier.notify_service_error("Deviation morning summary", e)
                morning_summary_sent = True

            # Sleep until market close; loop will detect session end and send EOD summary.
            wait = seconds_until_market_close()
            log.info("Sleeping %.0fs until market close.", wait)
            await asyncio.sleep(max(wait, 60))
