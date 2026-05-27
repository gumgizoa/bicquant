"""Deviation alert queries."""

from decimal import Decimal

from shared.db import session
from shared.models import DeviationAlert


async def save_alert(
    target_code: str,
    target_name: str,
    current: float,
    ma50: float,
    ratio: float,
) -> None:
    async with session() as s, s.begin():
        s.add(
            DeviationAlert(
                target_code=target_code,
                target_name=target_name,
                current_value=Decimal(str(current)),
                ma50=Decimal(str(ma50)),
                deviation_ratio=Decimal(str(ratio)),
            )
        )
