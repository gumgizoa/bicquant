import logging

import httpx
from shared.config import get_config

log = logging.getLogger(__name__)

cfg = get_config("monitor")

MARKET_NAME = {"kospi": "코스피", "kosdaq": "코스닥"}
EVENT_NAME = {
    "sell_triggered": "매도 사이드카 발동 🚨",
    "sell_released": "매도 사이드카 해제",
    "buy_triggered": "매수 사이드카 발동 🚀",
    "buy_released": "매수 사이드카 해제",
}
CB_EVENT_NAME = {
    "cb_l1_triggered": "서킷브레이크 1단계 발동 🚨",
    "cb_l1_released": "서킷브레이크 1단계 해제",
    "cb_l1_simul_close": "서킷브레이크 1단계 동시호가종료",
    "cb_l2_triggered": "서킷브레이크 2단계 발동 🚨🚨",
    "cb_l3_triggered": "서킷브레이크 3단계 발동 — 당일 장종료 🔴",
    "cb_l2_released": "서킷브레이크 2단계 해제",
    "cb_l2_simul_close": "서킷브레이크 2단계 동시호가종료",
}


async def send_telegram(message: str) -> None:
    try:
        url = f"https://api.telegram.org/bot{cfg.telegram.bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json={
                    "chat_id": cfg.telegram.chat_group_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
            )
            resp.raise_for_status()
    except Exception as e:
        log.error(f"Telegram send failed: {e}")


def format_sidecar_alert(market: str, event_type: str, index_info: dict) -> str:
    market_kr = MARKET_NAME.get(market, market)
    event_kr = EVENT_NAME.get(event_type, event_type)
    current = index_info.get("current", "N/A")
    change_pct = index_info.get("change_pct", "N/A")

    return "\n".join(
        [
            f"<b>{market_kr} {event_kr}</b>",
            "",
            f"현재 지수: {current}",
            f"전일 대비: {change_pct}%",
        ]
    )


def format_circuit_breaker_alert(market: str, event_type: str, index_info: dict) -> str:
    market_kr = MARKET_NAME.get(market, market)
    event_kr = CB_EVENT_NAME.get(event_type, event_type)
    current = index_info.get("current", "N/A")
    change_pct = index_info.get("change_pct", "N/A")

    return "\n".join(
        [
            f"<b>{market_kr} {event_kr}</b>",
            "",
            f"현재 지수: {current}",
            f"전일 대비: {change_pct}%",
        ]
    )


def format_deviation_alert(code: str, name: str, current: float, ma50: float, ratio: float) -> str:
    return (
        f"📊 <b>이격도 알림</b>\n\n"
        f"종목: {name} ({code})\n"
        f"현재가: {current:,.2f}\n"
        f"50일 MA: {ma50:,.2f}\n"
        f"이격도: <b>{ratio:.1f}</b> (기준: {cfg.deviation.threshold:.0f})"
    )
