"""Monitor service entry point.

Runs three concurrent tasks, each under a supervisor:
  - sidecar: subscribes to JIF WebSocket for real-time sidecar/circuit-breaker events
  - deviation: polls every DEVIATION_POLL_INTERVAL seconds for deviation ratio alerts
  - dart: polls DART for new listed-company disclosures

Each task is wrapped by ``_supervise`` so that an unhandled exception in one task
restarts only that task (with exponential backoff) instead of tearing down the
whole ``TaskGroup`` and exiting the process. Letting the process exit would have
Docker's ``restart: unless-stopped`` policy relaunch the container, which
re-fires the deviation startup summary at an arbitrary time of day.
"""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable

from shared import db

from monitor import notifier
from monitor.dart import monitor_dart_disclosures
from monitor.deviation import monitor_deviation
from monitor.sidecar import monitor_sidecar

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(name)-30s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


async def _supervise(
    name: str,
    factory: Callable[[], Awaitable[None]],
    *,
    base_delay: float = 5.0,
    max_delay: float = 300.0,
) -> None:
    """Run ``factory()`` forever, restarting it on failure with backoff.

    A monitor coroutine is not expected to return; if it crashes we log and
    restart it after a delay that grows up to ``max_delay``. ``CancelledError``
    is re-raised so service shutdown still propagates.
    """
    delay = base_delay
    while True:
        try:
            await factory()
            log.warning("monitor task %r returned unexpectedly; restarting", name)
            delay = base_delay
        except asyncio.CancelledError:
            log.info("monitor task %r cancelled", name)
            raise
        except Exception as e:
            log.exception("monitor task %r crashed; restarting in %.0fs", name, delay)
            await notifier.notify_service_error(f"monitor task '{name}' crashed; restarting in {delay:.0f}s", e)
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)
            continue
        await asyncio.sleep(base_delay)


async def main() -> None:
    log.info("Monitor service starting")
    await db.init()
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_supervise("sidecar", monitor_sidecar), name="sidecar")
            tg.create_task(_supervise("deviation", monitor_deviation), name="deviation")
            tg.create_task(_supervise("dart", monitor_dart_disclosures), name="dart")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
