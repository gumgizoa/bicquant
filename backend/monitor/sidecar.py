"""JIF WebSocket monitor: detects sidecar and circuit-breaker events."""

import asyncio
import logging

from shared.config import get_config
from shared.queries import circuit_breaker as cb_q
from shared.queries import sidecar as sidecar_q

from lsapi import LSClient, LSWebSocketClient
from monitor import notifier

log = logging.getLogger(__name__)

cfg = get_config("monitor")

# jstatus → event_type
_JSTATUS = {
    "64": "sell_triggered",
    "65": "sell_released",
    "66": "buy_triggered",
    "67": "buy_released",
}

_MARKET = {"1": "kospi", "2": "kosdaq"}
_UPCODE = {"kospi": "001", "kosdaq": "301"}

# jstatus → event_type for KOSPI/KOSDAQ circuit breaker events
_CB_STATUS = {
    "61": "cb_l1_triggered",
    "62": "cb_l1_released",
    "63": "cb_l1_simul_close",
    "68": "cb_l2_triggered",
    "69": "cb_l3_triggered",
    "70": "cb_l2_released",
    "71": "cb_l2_simul_close",
}


async def _fetch_index_snapshot(client: LSClient, upcode: str) -> dict:
    """Fetch current index level and daily change for context."""
    try:
        resp = await client.call("t1511", {"t1511InBlock": {"upcode": upcode}})
        block = resp.block("t1511OutBlock") or {}
        current = float(block.get("pricejisu", 0))
        change_pct = float(block.get("diffjisu", 0))
        return {"current": f"{current:,.2f}", "change_pct": f"{change_pct:+.2f}"}
    except Exception as e:
        log.warning(f"Failed to fetch index snapshot (upcode={upcode}): {e}")
        return {}


async def monitor_sidecar() -> None:
    async with LSClient(cfg.ls_api.app_key, cfg.ls_api.app_secret) as rest:
        async with LSWebSocketClient(cfg.ls_api.app_key, cfg.ls_api.app_secret) as ws:
            log.info("JIF WebSocket connected, watching for sidecar events")

            async def on_jif(msg: dict) -> None:
                body = msg.get("body", {})
                jangubun = body.get("jangubun", "")
                jstatus = body.get("jstatus", "")

                if jangubun not in _MARKET:
                    return

                market = _MARKET[jangubun]

                if jstatus in _JSTATUS:
                    event_type = _JSTATUS[jstatus]
                    log.info(f"Sidecar event: {market} {event_type}")

                    index_info = await _fetch_index_snapshot(rest, _UPCODE[market])

                    await sidecar_q.save_event(market, event_type, "", {**body, **index_info})

                    alert = notifier.format_sidecar_alert(market, event_type, index_info)
                    await notifier.send_telegram(alert)

                elif jstatus in _CB_STATUS:
                    event_type = _CB_STATUS[jstatus]
                    log.info(f"Circuit breaker event: {market} {event_type}")

                    index_info = await _fetch_index_snapshot(rest, _UPCODE[market])

                    await cb_q.save_event(market, event_type, "", {**body, **index_info})

                    alert = notifier.format_circuit_breaker_alert(market, event_type, index_info)
                    await notifier.send_telegram(alert)

            await ws.subscribe("JIF", "", callback=on_jif)
            # LSWebSocketClient handles reconnection automatically; wait here indefinitely
            await asyncio.Future()
