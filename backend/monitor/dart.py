"""DART disclosure monitor.

Two tasks per trading day:
1. Opening summary (7:30 KST): fetches all listed-company disclosures for today
   and sends a count summary to Telegram.
2. Every 10 minutes (DART disclosure hours): checks for new listed-company disclosures
   and sends individual notifications for each new entry.

Listed companies are defined as corp_cls in {'유' (KOSPI), '코' (KOSDAQ)}.
"""

import asyncio
import datetime
import logging
import zoneinfo

from dartapi.dart_utils import list_dart_disclosures_by_date
from monitor import notifier

log = logging.getLogger(__name__)

_KST = zoneinfo.ZoneInfo("Asia/Seoul")
_LISTED_CLS = frozenset({"유", "코"})
_DART_OPEN = datetime.time(7, 30)
_DART_CLOSE = datetime.time(18, 0)

# Only disclosures whose report name (report_nm) contains one of these substrings
# are notified. Keywords are intentionally broad enough to also catch the
# correction ([기재정정]/[첨부정정]), 자율공시, and 자회사/종속회사 variants of each
# subject, while staying specific enough to exclude unrelated filings.
#   - 증자(유상/무상/유무상)결정       -> "증자결정"
#   - 중대재해발생                      -> "중대재해발생"
#   - 최대주주변경                      -> "최대주주변경"
#   - 단일판매ㆍ공급계약체결 / 수주      -> "공급계약체결", "수주"
#   - 매출액또는손익구조30%이상변동     -> "손익구조"
#   - 주식소각결정                      -> "주식소각"
#   - 신규시설투자등                    -> "신규시설투자"
_SUBJECT_KEYWORDS = frozenset(
    {
        "증자결정",
        "중대재해발생",
        "최대주주변경",
        "공급계약체결",
        "수주",
        "손익구조",
        "주식소각",
        "신규시설투자",
    }
)

_POLL_INTERVAL = 600  # 10 minutes
_MORNING_END_PAGE = 50  # enough to cover all pre-market disclosures
_POLL_END_PAGE = 3  # newest disclosures always appear on the first pages


def _matches_subject(report_nm: str) -> bool:
    """Return True if report_nm relates to one of the monitored disclosure subjects."""
    return any(kw in report_nm for kw in _SUBJECT_KEYWORDS)


def _now_kst() -> datetime.datetime:
    return datetime.datetime.now(_KST)


def _is_dart_disclosure_hours() -> bool:
    """Return True during same-day DART disclosure hours (Mon-Fri 07:30-18:00 KST)."""
    now = _now_kst()
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return _DART_OPEN <= now.time() < _DART_CLOSE


def _seconds_until_dart_open() -> float:
    """Return seconds until the next DART disclosure open (07:30 KST on a weekday)."""
    now = _now_kst()
    candidate = now.replace(hour=_DART_OPEN.hour, minute=_DART_OPEN.minute, second=0, microsecond=0)
    if now >= candidate:
        candidate += datetime.timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += datetime.timedelta(days=1)
    return (candidate - now).total_seconds()


# Tracks rcept_no values already notified; cleared after DART disclosure hours.
_seen_rcept_nos: set[str] = set()


async def _fetch_disclosures(date_str: str, end_page: int) -> list[dict]:
    """Fetch listed-company disclosures for date_str up to end_page pages.

    Args:
        date_str: Date in YYYYMMDD format.
        end_page: Maximum page to fetch; function stops earlier if no data found.

    Returns:
        Filtered list of disclosure dicts: listed companies whose report name
        matches one of the monitored subjects (see _SUBJECT_KEYWORDS).
    """
    all_disclosures = await asyncio.to_thread(list_dart_disclosures_by_date, date_str, 1, end_page)
    return [d for d in all_disclosures if d.get("corp_cls") in _LISTED_CLS and _matches_subject(d.get("report_nm", ""))]


async def _send_morning_summary(date_str: str) -> None:
    """Fetch all today's disclosures, populate seen set, and send count to Telegram."""
    try:
        disclosures = await _fetch_disclosures(date_str, _MORNING_END_PAGE)
    except Exception as e:
        log.error("DART morning summary fetch error: %s", e)
        await notifier.notify_service_error("DART morning summary fetch", e)
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
        await notifier.notify_service_error("DART poll fetch", e)
        return

    for d in disclosures:
        rcept_no = d["rcept_no"]
        if rcept_no not in _seen_rcept_nos:
            _seen_rcept_nos.add(rcept_no)
            msg = notifier.format_dart_new_disclosure(d)
            await notifier.send_telegram(msg)


async def monitor_dart_disclosures() -> None:
    """Main loop: opening summary at DART open, then poll every 10 minutes."""
    morning_sent = False

    while True:
        if not _is_dart_disclosure_hours():
            if morning_sent:
                morning_sent = False
                _seen_rcept_nos.clear()

            wait = _seconds_until_dart_open()
            log.info("DART disclosure hours closed. Waiting %.0fs until next open.", wait)
            await asyncio.sleep(wait)
            continue

        today = _now_kst().strftime("%Y%m%d")

        if not morning_sent:
            try:
                await _send_morning_summary(today)
            except Exception as e:
                log.error("DART morning summary error: %s", e)
                await notifier.notify_service_error("DART morning summary", e)
            morning_sent = True
        else:
            await _check_new_disclosures(today)

        await asyncio.sleep(_POLL_INTERVAL)
