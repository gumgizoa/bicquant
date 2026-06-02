"""DART disclosure monitor.

Two tasks per trading day:
1. Morning summary (9:00 KST): fetches all listed-company disclosures for today
   and sends a count summary to Telegram.
2. Every 10 minutes (market hours): checks for new listed-company disclosures
   and sends individual notifications for each new entry.

Listed companies are defined as corp_cls in {'유' (KOSPI), '코' (KOSDAQ)}.
"""

import asyncio
import datetime
import logging
import zoneinfo

from dartapi.dart_utils import list_dart_disclosures_by_date
from monitor import notifier
from monitor.market_hours import is_market_hours, seconds_until_market_open

log = logging.getLogger(__name__)

_KST = zoneinfo.ZoneInfo("Asia/Seoul")
_LISTED_CLS = frozenset({"유", "코"})

_POLL_INTERVAL = 600  # 10 minutes
_MORNING_END_PAGE = 50  # enough to cover all pre-market disclosures
_POLL_END_PAGE = 3  # newest disclosures always appear on the first pages

# Tracks rcept_no values already notified; cleared on each market close.
_seen_rcept_nos: set[str] = set()


async def _fetch_disclosures(date_str: str, end_page: int) -> list[dict]:
    """Fetch listed-company disclosures for date_str up to end_page pages.

    Args:
        date_str: Date in YYYYMMDD format.
        end_page: Maximum page to fetch; function stops earlier if no data found.

    Returns:
        Filtered list of disclosure dicts (listed companies only).
    """
    all_disclosures = await asyncio.to_thread(list_dart_disclosures_by_date, date_str, 1, end_page)
    return [d for d in all_disclosures if d.get("corp_cls") in _LISTED_CLS]


async def _send_morning_summary(date_str: str) -> None:
    """Fetch all today's disclosures, populate seen set, and send count to Telegram."""
    try:
        disclosures = await _fetch_disclosures(date_str, _MORNING_END_PAGE)
    except Exception as e:
        log.error("DART morning summary fetch error: %s", e)
        return

    for d in disclosures:
        _seen_rcept_nos.add(d["rcept_no"])

    by_cls: dict[str, int] = {}
    for d in disclosures:
        cls = d.get("corp_cls", "기타")
        by_cls[cls] = by_cls.get(cls, 0) + 1

    msg = notifier.format_dart_daily_count(date_str, len(disclosures), by_cls)
    await notifier.send_telegram(msg)


async def _check_new_disclosures(date_str: str) -> None:
    """Fetch recent disclosures and send a notification for each unseen one."""
    try:
        disclosures = await _fetch_disclosures(date_str, _POLL_END_PAGE)
    except Exception as e:
        log.error("DART poll fetch error: %s", e)
        return

    for d in disclosures:
        rcept_no = d["rcept_no"]
        if rcept_no not in _seen_rcept_nos:
            _seen_rcept_nos.add(rcept_no)
            msg = notifier.format_dart_new_disclosure(d)
            await notifier.send_telegram(msg)


async def monitor_dart_disclosures() -> None:
    """Main loop: morning summary at market open, then poll every 10 minutes."""
    morning_sent = False

    while True:
        if not is_market_hours():
            if morning_sent:
                morning_sent = False
                _seen_rcept_nos.clear()

            wait = seconds_until_market_open()
            log.info("Market closed. DART monitor waiting %.0fs until next open.", wait)
            await asyncio.sleep(wait)
            continue

        today = datetime.datetime.now(_KST).strftime("%Y%m%d")

        if not morning_sent:
            try:
                await _send_morning_summary(today)
            except Exception as e:
                log.error("DART morning summary error: %s", e)
            morning_sent = True
        else:
            await _check_new_disclosures(today)

        await asyncio.sleep(_POLL_INTERVAL)
