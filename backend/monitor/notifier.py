import logging

import httpx

from monitor import config

log = logging.getLogger(__name__)

_TELEGRAM_URL = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"

MARKET_NAME = {"kospi": "코스피", "kosdaq": "코스닥"}
EVENT_NAME = {
    "sell_triggered": "매도 사이드카 발동 🚨",
    "sell_released": "매도 사이드카 해제",
    "buy_triggered": "매수 사이드카 발동 🚀",
    "buy_released": "매수 사이드카 해제",
}


async def send_telegram(message: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                _TELEGRAM_URL,
                json={
                    "chat_id": config.TELEGRAM_ALERT_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML",
                },
            )
            resp.raise_for_status()
    except Exception as e:
        log.error(f"Telegram send failed: {e}")


def _build_llm():
    from langchain_openai import AzureChatOpenAI

    return AzureChatOpenAI(
        model="gpt-5",
        openai_api_key=config.AZURE_OPENAI_API_KEY,
        openai_api_version=config.AZURE_OPENAI_API_VERSION,
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        azure_deployment=config.AZURE_OPENAI_DEPLOYMENT,
        max_tokens=400,
    )


async def analyze_sidecar(market: str, event_type: str, index_info: dict) -> str:
    try:
        from langchain_core.messages import HumanMessage

        market_kr = MARKET_NAME.get(market, market)
        event_kr = EVENT_NAME.get(event_type, event_type)
        current = index_info.get("current", "N/A")
        change_pct = index_info.get("change_pct", "N/A")

        prompt = (
            f"{market_kr} 시장에서 {event_kr}가 발생했습니다.\n\n"
            f"현재 지수: {current}\n"
            f"전일 대비: {change_pct}%\n\n"
            "사이드카 발동 원인과 현재 시장 상황을 3-4문장으로 간결하게 분석해주세요."
        )
        response = _build_llm().invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        log.error(f"LLM analysis failed: {e}")
        return ""


def format_sidecar_alert(market: str, event_type: str, index_info: dict, analysis: str) -> str:
    market_kr = MARKET_NAME.get(market, market)
    event_kr = EVENT_NAME.get(event_type, event_type)
    current = index_info.get("current", "N/A")
    change_pct = index_info.get("change_pct", "N/A")

    lines = [
        f"<b>{market_kr} {event_kr}</b>",
        "",
        f"현재 지수: {current}",
        f"전일 대비: {change_pct}%",
    ]
    if analysis:
        lines += ["", "📝 분석", analysis]
    return "\n".join(lines)


def format_deviation_alert(code: str, name: str, current: float, ma50: float, ratio: float) -> str:
    return (
        f"📊 <b>이격도 알림</b>\n\n"
        f"종목: {name} ({code})\n"
        f"현재가: {current:,.2f}\n"
        f"50일 MA: {ma50:,.2f}\n"
        f"이격도: <b>{ratio:.1f}</b> (기준: {config.DEVIATION_THRESHOLD:.0f})"
    )
