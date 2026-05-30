"""Periodic deviation ratio monitor.

Deviation ratio = (current price / 50-day moving average) x 100.
Alerts when ratio >= deviation.threshold (default 130).
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import numpy as np
from shared.config import get_config
from shared.queries import deviation as deviation_q
from shared.queries import watchlist as watchlist_q

from lsapi import LSClient
from monitor import notifier

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

cfg = get_config("monitor")


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
    resp = await client.call(
        "t8419",
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
    return [float(r["close"]) for r in (resp.block("t8419OutBlock1") or []) if r.get("close")]


async def _fetch_stock_closes(client: LSClient, shcode: str, count: int = 60) -> list[float]:
    resp = await client.call(
        "t8451",
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
    return [float(r["close"]) for r in (resp.block("t8451OutBlock1") or []) if r.get("close")]


async def _fetch_stock_name(client: LSClient, shcode: str) -> str:
    try:
        resp = await client.call("t1101", shcode=shcode)
        return (resp.block("t1101OutBlock") or {}).get("hname", shcode)
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

    if ratio >= cfg.deviation.threshold:
        log.info(f"DEVIATION ALERT: {name} ({code}) ratio={ratio:.1f}")
        await deviation_q.save_alert(code, name, current, ma50, ratio)
        alert = notifier.format_deviation_alert(code, name, current, ma50, ratio)
        await notifier.send_telegram(alert)


async def monitor_deviation() -> None:
    async with LSClient(cfg.ls_api.app_key, cfg.ls_api.app_secret) as client:
        while True:
            if not _is_market_hours():
                await asyncio.sleep(60)
                continue

            try:
                for upcode, name in _INDICES:
                    closes = await _fetch_index_closes(client, upcode)
                    await _evaluate(upcode, name, closes)

                for shcode in await watchlist_q.get_active_codes():
                    name = await _fetch_stock_name(client, shcode)
                    closes = await _fetch_stock_closes(client, shcode)
                    await _evaluate(shcode, name, closes)

            except Exception as e:
                log.error(f"Deviation poll error: {e}")

            await asyncio.sleep(cfg.deviation.poll_interval)
