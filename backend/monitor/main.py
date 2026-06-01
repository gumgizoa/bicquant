"""Monitor service entry point.

Runs two concurrent tasks:
  - sidecar: subscribes to JIF WebSocket for real-time sidecar/circuit-breaker events
  - deviation: polls every DEVIATION_POLL_INTERVAL seconds for deviation ratio alerts
"""

import asyncio
import logging

from shared import db

from monitor.dart_monitor import monitor_dart_disclosures
from monitor.deviation import monitor_deviation
from monitor.sidecar import monitor_sidecar

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-30s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


async def main() -> None:
    log.info("Monitor service starting")
    await db.init()
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(monitor_sidecar(), name="sidecar")
            tg.create_task(monitor_deviation(), name="deviation")
            tg.create_task(monitor_dart_disclosures(), name="dart")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
