"""JIF WebSocket monitor: detects sidecar and circuit-breaker events."""

import asyncio
import logging
from functools import partial

from shared.config import get_config
from shared.queries import circuit_breaker as cb_q
from shared.queries import sidecar as sidecar_q

from lsapi import AsyncLSClient as LSClient
from lsapi import LSWebSocketClient
from monitor import notifier
from monitor.market_hours import is_market_hours, seconds_until_market_close, seconds_until_market_open

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

# Delay before reconnecting after a WebSocket/session error.
_RECONNECT_DELAY = 5.0

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

# Common market-session status codes (spec: jangubun 1=KOSPI, 2=KOSDAQ)
_JSTATUS_COMMON = {
    "11": "장전 동시호가 개시",
    "21": "장 시작",
    "22": "장 개시 10초 전",
    "23": "장 개시 1분 전",
    "24": "장 개시 5분 전",
    "25": "장 개시 10분 전",
    "31": "장후 동시호가 개시",
    "41": "장 마감",
    "42": "장 마감 10초 전",
    "43": "장 마감 1분 전",
    "44": "장 마감 5분 전",
    "51": "시간외 종가매매 개시",
    "52": "시간외 단일가매매 개시",
    "54": "시간외 단일가매매 종료",
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
        log.warning("Failed to fetch index snapshot (upcode=%s): %s", upcode, e)
        return {}


async def handle_jif(rest: LSClient, msg: dict) -> None:
    """Dispatch a single JIF realtime frame to sidecar / circuit-breaker handling.

    Routing:
        jangubun → market (1=kospi, 2=kosdaq); other values are ignored.
        jstatus  → sidecar event (_JSTATUS) or circuit-breaker event (_CB_STATUS);
                   unknown values are ignored.

    For a recognised event it fetches an index snapshot, persists the event, and
    sends a Telegram alert. ``rest`` is the active LS API client used for the
    snapshot.
    """
    body = msg.get("body") or {}
    jangubun = body.get("jangubun", "")
    jstatus = body.get("jstatus", "")

    log.info("JIF frame: jangubun=%r jstatus=%r", jangubun, jstatus)

    if not jangubun and not jstatus:
        return  # ACK 메시지 (body 없음)

    market = _MARKET.get(jangubun, jangubun)  # 알 수 없는 jangubun은 값 그대로 사용

    if jstatus in _JSTATUS and jangubun in _MARKET:
        event_type = _JSTATUS[jstatus]
        log.info("Sidecar event: %s %s", market, event_type)
        index_info = await _fetch_index_snapshot(rest, _UPCODE[market])
        try:
            await sidecar_q.save_event(market, event_type, "", {**body, **index_info})
        except Exception:
            log.exception("Failed to persist sidecar event (%s %s); sending alert anyway", market, event_type)
        alert = notifier.format_sidecar_alert(market, event_type, index_info)
        await notifier.send_telegram(alert)

    elif jstatus in _CB_STATUS and jangubun in _MARKET:
        event_type = _CB_STATUS[jstatus]
        log.info("Circuit breaker event: %s %s", market, event_type)
        index_info = await _fetch_index_snapshot(rest, _UPCODE[market])
        try:
            await cb_q.save_event(market, event_type, "", {**body, **index_info})
        except Exception:
            log.exception("Failed to persist circuit-breaker event (%s %s); sending alert anyway", market, event_type)
        alert = notifier.format_circuit_breaker_alert(market, event_type, index_info)
        await notifier.send_telegram(alert)

    else:
        label = _JSTATUS_COMMON.get(jstatus, f"알 수 없는 상태 ({jstatus})")
        log.info("JIF status: jangubun=%s jstatus=%s %s", jangubun, jstatus, label)
        if jangubun in _MARKET:
            await notifier.send_telegram(notifier.format_jif_status(market, label))


async def monitor_sidecar() -> None:
    while True:
        if not is_market_hours():
            wait = seconds_until_market_open()
            log.info("Market closed. Waiting %.0fs until next open.", wait)
            await asyncio.sleep(wait)
            continue

        try:
            async with LSClient(cfg.ls_api.app_key, cfg.ls_api.app_secret) as rest:
                async with LSWebSocketClient(cfg.ls_api.app_key, cfg.ls_api.app_secret) as ws:
                    log.info("JIF WebSocket connected, watching for sidecar/CB events")

                    await ws.subscribe("JIF", "0", callback=partial(handle_jif, rest))

                    secs = seconds_until_market_close()
                    log.info("Monitoring until market close in %.0fs.", secs)
                    await asyncio.sleep(secs)

            log.info("Market session ended. Disconnecting.")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # WebSocket drops, token refresh failures, and transient network
            # errors are expected over a long session — reconnect rather than
            # letting the exception bubble up and crash the monitor process.
            log.exception("Sidecar WebSocket error; reconnecting in %.0fs", _RECONNECT_DELAY)
            await notifier.notify_service_error(f"Sidecar WebSocket; reconnecting in {_RECONNECT_DELAY:.0f}s", e)
            await asyncio.sleep(_RECONNECT_DELAY)
