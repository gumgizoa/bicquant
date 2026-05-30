"""Circuit breaker event queries."""

from typing import Any

from shared.db import session
from shared.models import CircuitBreakerEvent


async def save_event(
    market: str,
    event_type: str,
    analysis: str,
    raw_data: dict[str, Any],
) -> None:
    async with session() as s, s.begin():
        s.add(
            CircuitBreakerEvent(
                market=market,
                event_type=event_type,
                analysis=analysis,
                raw_data=raw_data,
            )
        )
