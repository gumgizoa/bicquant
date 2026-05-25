"""Periodic deviation ratio monitor.

Deviation ratio = (current price / 50-day moving average) x 100.
Alerts when ratio >= DEVIATION_THRESHOLD (default 130).
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import numpy as np

from lsapi import LSClient
from monitor import config, db, notifier

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# KOSPI=001, KOSDAQ=301
_INDICES = [
    ("001", "코스피"),
    ("301", "코스닥"),
]


def _is_market_hours() -> bool:
    now = datetime.now(KST)
    if now.weekday() >= 5:  # Saturday / Sunday
        return False
    t = (now.hour, now.minute)
    return (9, 0) <= t <= (15, 30)


async def _fetch_index_closes(client: LSClient, upcode: str, count: int = 60) -> list[float]:
    data = await client.request(
        "t8419",
        "/indtp/chart",
        {
            "t8419InBlock": {
                "shcode": upcode,
                "gubun": "1",  # daily bars
                "qrycnt": str(count),
                "sdate": "",
                "edate": "99999999",
                "cts_date": "",
                "comp_yn": "N",
            }
        },
    )
    return [float(r["close"]) for r in data.get("t8419OutBlock1", []) if r.get("close")]


async def _fetch_stock_closes(client: LSClient, shcode: str, count: int = 60) -> list[float]:
    data = await client.request(
        "t8451",
        "/stock/chart",
        {
            "t8451InBlock": {
                "shcode": shcode,
                "gubun": "0",  # daily bars
                "qrycnt": str(count),
                "sdate": "",
                "edate": "99999999",
                "cts_date": "",
                "comp_yn": "N",
                "sujung": "1",  # adjusted price
                "exchgubun": "K",
            }
        },
    )
    return [float(r["close"]) for r in data.get("t8451OutBlock1", []) if r.get("close")]


async def _fetch_stock_name(client: LSClient, shcode: str) -> str:
    try:
        data = await client.request(
            "t1101",
            "/stock/market-data",
            {"t1101InBlock": {"shcode": shcode}},
        )
        return data.get("t1101OutBlock", {}).get("hname", shcode)
    except Exception:
        return shcode


async def _evaluate(code: str, name: str, closes: list[float]) -> None:
    """Compute deviation ratio and alert if over threshold."""
    if len(closes) < 51:
        log.warning(f"{name} ({code}): only {len(closes)} days of data, need 51")
        return

    # closes[-1] is today's latest price; MA50 uses the 50 days before it
    current = closes[-1]
    ma50 = float(np.mean(closes[-51:-1]))
    if ma50 == 0:
        return

    ratio = current / ma50 * 100
    log.debug(f"{name}: current={current:.2f}, MA50={ma50:.2f}, deviation={ratio:.1f}")

    if ratio >= config.DEVIATION_THRESHOLD:
        log.info(f"DEVIATION ALERT: {name} ({code}) ratio={ratio:.1f}")
        await db.save_deviation_alert(code, name, current, ma50, ratio)
        alert = notifier.format_deviation_alert(code, name, current, ma50, ratio)
        await notifier.send_telegram(alert)


async def monitor_deviation() -> None:
    async with LSClient(config.LS_APP_KEY, config.LS_APP_SECRET) as client:
        while True:
            if not _is_market_hours():
                await asyncio.sleep(60)
                continue

            try:
                for upcode, name in _INDICES:
                    closes = await _fetch_index_closes(client, upcode)
                    await _evaluate(upcode, name, closes)

                for shcode in config.STOCK_CODES:
                    name = await _fetch_stock_name(client, shcode)
                    closes = await _fetch_stock_closes(client, shcode)
                    await _evaluate(shcode, name, closes)

            except Exception as e:
                log.error(f"Deviation poll error: {e}")

            await asyncio.sleep(config.DEVIATION_POLL_INTERVAL)
