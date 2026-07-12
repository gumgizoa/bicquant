"""Shared fixtures for the backend test suite — live integration only.

These tests hit the real services in the **dev** environment:
  - LS Open API  (LS_OPENAPI_APP_KEY / LS_OPENAPI_APP_SECRET)
  - DART API     (DART_API_KEY)
  - FRED API     (FRED_API_KEY)
  - Postgres     (DATABASE_URL — the dev docker-compose database)
  - Telegram     (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_GROUP_ID — dev chat)

There are no mocks of these services. A test that needs a service simply
requests the matching fixture; if that service is unavailable the fixture
calls ``pytest.skip`` so the suite stays green on a partial dev stack.

All live tests are marked ``slow`` so the pre-push gate (``pytest -m "not slow"``)
stays fast and offline. Run them on demand with::

    uv run pytest backend/tests -m slow

Everything is exposed as fixtures (not importable symbols) because both
``./tests`` and ``./backend/tests`` are packages named ``tests`` — importing
``tests.conftest`` would be ambiguous.
"""

import asyncio
import datetime
import os
import zoneinfo

import pytest
from dotenv import load_dotenv

# Load repo-root .env first, then any local .env override.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_REPO_ROOT, ".env"))
load_dotenv()

_LS_KEY = os.getenv("LS_OPENAPI_APP_KEY", "")
_LS_SECRET = os.getenv("LS_OPENAPI_APP_SECRET", "")
_HAVE_LS = bool(_LS_KEY and _LS_SECRET)
_HAVE_DART = bool(os.getenv("DART_API_KEY"))
_HAVE_FRED = bool(os.getenv("FRED_API_KEY"))
_HAVE_DB = bool(os.getenv("DATABASE_URL"))
_HAVE_TG = bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_GROUP_ID"))

_KST = zoneinfo.ZoneInfo("Asia/Seoul")


@pytest.fixture(autouse=True)
async def _rate_limit(request):
    """Pause before each live (``slow``) test to stay within LS API TPS limits."""
    if request.node.get_closest_marker("slow"):
        await asyncio.sleep(1.0)
    yield


@pytest.fixture
def recent_trading_day() -> str:
    """Most recent weekday in KST as ``YYYYMMDD`` (good enough for DART queries)."""
    d = datetime.datetime.now(_KST).date()
    while d.weekday() >= 5:  # Sat=5, Sun=6
        d -= datetime.timedelta(days=1)
    return d.strftime("%Y%m%d")


@pytest.fixture
def dart():
    """Gate a test on DART_API_KEY being present."""
    if not _HAVE_DART:
        pytest.skip("DART_API_KEY not set")


@pytest.fixture
def fred():
    """Gate a test on FRED_API_KEY being present."""
    if not _HAVE_FRED:
        pytest.skip("FRED_API_KEY not set")


@pytest.fixture
def telegram():
    """Gate a test on Telegram (dev chat) credentials being present."""
    if not _HAVE_TG:
        pytest.skip("Telegram credentials not set")


@pytest.fixture
async def ls_client():
    """A live :class:`AsyncLSClient` bound to the dev credentials."""
    if not _HAVE_LS:
        pytest.skip("LS API credentials not set")
    from lsapi import AsyncLSClient

    async with AsyncLSClient(_LS_KEY, _LS_SECRET) as client:
        yield client


class _LiveDB:
    """Thin handle over ``shared.db`` with row-scoping helpers for cleanup."""

    def __init__(self, module) -> None:
        self._db = module

    def session(self):
        return self._db.session()

    async def max_id(self, model) -> int:
        from sqlalchemy import func, select

        async with self._db.session() as s:
            return (await s.execute(select(func.coalesce(func.max(model.id), 0)))).scalar() or 0

    async def rows_after(self, model, after_id: int) -> list:
        from sqlalchemy import select

        async with self._db.session() as s:
            return list((await s.execute(select(model).where(model.id > after_id))).scalars().all())

    async def delete_after(self, model, after_id: int) -> None:
        from sqlalchemy import delete

        async with self._db.session() as s, s.begin():
            await s.execute(delete(model).where(model.id > after_id))


@pytest.fixture
async def live_db():
    """Initialise the real (dev) DB engine; ensure tables exist; dispose after.

    Skips (not fails) when ``DATABASE_URL`` is unset or the database is
    unreachable.
    """
    if not _HAVE_DB:
        pytest.skip("DATABASE_URL not set")

    from shared import db
    from shared.models.base import Base

    try:
        await db.init()
        async with db.engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:  # noqa: BLE001
        await db.close()
        pytest.skip(f"dev database unreachable: {e}")

    yield _LiveDB(db)
    await db.close()
