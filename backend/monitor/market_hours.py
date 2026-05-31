"""Korean stock market hours utilities (KST, Mon–Fri 09:00–15:30)."""

import datetime
import zoneinfo

_KST = zoneinfo.ZoneInfo("Asia/Seoul")
_MARKET_OPEN = datetime.time(9, 0)
_MARKET_CLOSE = datetime.time(15, 30)


def _now_kst() -> datetime.datetime:
    return datetime.datetime.now(_KST)


def is_market_hours() -> bool:
    """Return True if current KST time is within regular trading hours (Mon–Fri 09:00–15:30)."""
    now = _now_kst()
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return _MARKET_OPEN <= now.time() <= _MARKET_CLOSE


def seconds_until_market_open() -> float:
    """Return seconds until the next 09:00 KST on a weekday."""
    now = _now_kst()
    candidate = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now >= candidate:
        candidate += datetime.timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += datetime.timedelta(days=1)
    return (candidate - now).total_seconds()


def seconds_until_market_close() -> float:
    """Return seconds until 15:30 KST today (0 if already past)."""
    now = _now_kst()
    close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return max(0.0, (close - now).total_seconds())
