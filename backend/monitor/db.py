import json
import logging

import asyncpg

from monitor import config

log = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init() -> None:
    global _pool
    _pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=1, max_size=5)
    await _create_tables()
    log.info("DB pool ready")


async def _create_tables() -> None:
    assert _pool is not None
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sidecar_events (
                id          SERIAL PRIMARY KEY,
                occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                market      VARCHAR(10)  NOT NULL,
                event_type  VARCHAR(20)  NOT NULL,
                analysis    TEXT,
                raw_data    JSONB
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS deviation_alerts (
                id             SERIAL PRIMARY KEY,
                occurred_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                target_code    VARCHAR(20)  NOT NULL,
                target_name    VARCHAR(100) NOT NULL,
                current_value  NUMERIC      NOT NULL,
                ma50           NUMERIC      NOT NULL,
                deviation_ratio NUMERIC     NOT NULL
            )
        """)


async def save_sidecar_event(market: str, event_type: str, analysis: str, raw_data: dict) -> None:
    assert _pool is not None
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO sidecar_events (market, event_type, analysis, raw_data)
            VALUES ($1, $2, $3, $4)
            """,
            market,
            event_type,
            analysis,
            json.dumps(raw_data, ensure_ascii=False),
        )


async def save_deviation_alert(target_code: str, target_name: str, current: float, ma50: float, ratio: float) -> None:
    assert _pool is not None
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO deviation_alerts (target_code, target_name, current_value, ma50, deviation_ratio)
            VALUES ($1, $2, $3, $4, $5)
            """,
            target_code,
            target_name,
            current,
            ma50,
            ratio,
        )


async def close() -> None:
    if _pool:
        await _pool.close()
