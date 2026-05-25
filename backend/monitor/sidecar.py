"""JIF WebSocket monitor: detects sidecar and circuit-breaker events."""

import asyncio
import logging

from lsapi import LSClient, LSWebSocketClient
from monitor import config, db, notifier

log = logging.getLogger(__name__)

# jstatus → (event_type, is_trigger)
_JSTATUS = {
    "64": ("sell_triggered", True),
    "65": ("sell_released", False),
    "66": ("buy_triggered", True),
    "67": ("buy_released", False),
}

_MARKET = {"1": "kospi", "2": "kosdaq"}


async def _fetch_index_snapshot(upcode: str) -> dict:
    """Fetch current index level and daily change for context."""
    try:
        async with LSClient(config.LS_APP_KEY, config.LS_APP_SECRET) as client:
            data = await client.request(
                "t1511",
                "/indtp/market-data",
                {"t1511InBlock": {"upcode": upcode}},
            )
        block = data.get("t1511OutBlock", {})
        current = float(block.get("pricejisu", 0))
        change_pct = float(block.get("diffjisu", 0))
        return {"current": f"{current:,.2f}", "change_pct": f"{change_pct:+.2f}"}
    except Exception as e:
        log.warning(f"Failed to fetch index snapshot (upcode={upcode}): {e}")
        return {}


_UPCODE = {"kospi": "001", "kosdaq": "301"}


async def monitor_sidecar() -> None:
    while True:
        try:
            async with LSWebSocketClient(config.LS_APP_KEY, config.LS_APP_SECRET) as ws:
                log.info("JIF WebSocket connected, watching for sidecar events")
                async for msg in ws.subscribe("JIF", {"tr_key": ""}):
                    body = msg.get("body", {})
                    jangubun = body.get("jangubun", "")
                    jstatus = body.get("jstatus", "")

                    if jstatus not in _JSTATUS or jangubun not in _MARKET:
                        continue

                    event_type, is_trigger = _JSTATUS[jstatus]
                    market = _MARKET[jangubun]
                    log.info(f"Sidecar event: {market} {event_type}")

                    index_info = await _fetch_index_snapshot(_UPCODE[market])

                    analysis = ""
                    if is_trigger:
                        analysis = await notifier.analyze_sidecar(market, event_type, index_info)

                    await db.save_sidecar_event(market, event_type, analysis, {**body, **index_info})

                    alert = notifier.format_sidecar_alert(market, event_type, index_info, analysis)
                    await notifier.send_telegram(alert)

        except Exception as e:
            log.error(f"JIF WebSocket error: {e}. Reconnecting in 30s...")
            await asyncio.sleep(30)
