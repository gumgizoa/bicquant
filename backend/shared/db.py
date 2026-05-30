"""SQLAlchemy async engine and session factory shared by all services.

Lifecycle
---------
Each service entrypoint calls ``await db.init()`` at startup and
``await db.close()`` at shutdown. After init, sessions are obtained via:

    async with db.session() as session:
        ...

For FastAPI handlers, use ``Depends(db.get_session)`` instead — it yields
a session scoped to the request.

The engine uses the asyncpg driver. ``DATABASE_URL`` may be specified as
either ``postgresql://...`` or ``postgresql+asyncpg://...`` — the former
is rewritten transparently.
"""

import logging
import os
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

log = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _async_url(url: str) -> str:
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def init() -> None:
    global _engine, _session_factory
    if _engine is not None:
        return
    load_dotenv()
    url = _async_url(os.environ["DATABASE_URL"])
    _engine = create_async_engine(url, pool_size=5, max_overflow=0)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    log.info("DB engine ready")


async def close() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def session() -> AsyncSession:
    """Return a new ``AsyncSession``. Use as ``async with db.session() as s:``."""
    assert _session_factory is not None, "DB not initialised — call await shared.db.init() first"
    return _session_factory()


def engine() -> AsyncEngine:
    assert _engine is not None, "DB not initialised — call await shared.db.init() first"
    return _engine


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a request-scoped session."""
    async with session() as s:
        yield s
