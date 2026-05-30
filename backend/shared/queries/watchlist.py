"""Watchlist domain queries.

Each function opens its own session/transaction. If you need multiple
operations in one transaction, refactor to take ``session: AsyncSession``
as a parameter.
"""

import logging

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from shared.db import session
from shared.models import Watchlist

log = logging.getLogger(__name__)


async def get_active_codes() -> list[str]:
    """Active stock codes, ordered by insertion time."""
    async with session() as s:
        result = await s.execute(select(Watchlist.code).where(Watchlist.is_active.is_(True)).order_by(Watchlist.added_at))
        return [row[0] for row in result]


async def get_active_items() -> list[Watchlist]:
    """Active watchlist rows, ordered by insertion time."""
    async with session() as s:
        result = await s.execute(select(Watchlist).where(Watchlist.is_active.is_(True)).order_by(Watchlist.added_at))
        return list(result.scalars().all())


async def add(code: str, name: str | None = None) -> None:
    """Insert or re-activate a watchlist row. Updates name if provided."""
    async with session() as s, s.begin():
        stmt = pg_insert(Watchlist).values(code=code, name=name, is_active=True)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Watchlist.code],
            set_={
                "name": func.coalesce(stmt.excluded.name, Watchlist.name),
                "is_active": True,
            },
        )
        await s.execute(stmt)
    log.info(f"Watchlist: added {code!r} (name={name!r})")


async def remove(code: str) -> bool:
    """Soft-delete. Returns True if the code was active, False if not found."""
    async with session() as s, s.begin():
        result = await s.execute(update(Watchlist).where(Watchlist.code == code, Watchlist.is_active.is_(True)).values(is_active=False))
        affected = result.rowcount or 0
    log.info(f"Watchlist: removed {code!r} (affected={affected})")
    return affected > 0
