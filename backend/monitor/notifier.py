import logging
import traceback
from html import escape

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


async def notify_service_error(context: str, exc: BaseException) -> None:
    """Send a Telegram alert for monitor service errors."""
    await send_telegram(format_service_error_alert(context, exc))


def format_service_error_alert(context: str, exc: BaseException) -> str:
    """Format a service error notification for Telegram."""
    exc_name = type(exc).__name__
    exc_msg = str(exc) or "(no message)"
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    if len(tb) > 1800:
        tb = f"...\n{tb[-1800:]}"

    return "\n".join(
        [
            "⚠️ <b>서비스 에러</b>",
            "",
            f"위치: {escape(context)}",
            f"예외: <code>{escape(exc_name)}</code>",
            f"메시지: <code>{escape(exc_msg)}</code>",
            "",
            "<b>Traceback</b>",
            f"<pre>{escape(tb)}</pre>",
        ]
    )


def format_jif_status(market: str, label: str) -> str:
    market_kr = MARKET_NAME.get(market, market)
    return f"ℹ️ <b>{market_kr} {label}</b>"


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


def format_dart_daily_count(date_str: str, total: int, by_cls: dict) -> str:
    """Format the morning DART disclosure count summary.

    Args:
        date_str: Date string in YYYYMMDD format.
        total: Total listed-company disclosure count for the day.
        by_cls: Disclosure count per corp_cls (e.g. {'유': 8, '코': 7}).

    Returns:
        HTML-formatted Telegram message.
    """
    date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    cls_label = {"유": "유가증권", "코": "코스닥"}
    lines = [
        "📋 <b>오늘 공시 현황</b>",
        "",
        f"날짜: {date_fmt}",
        f"상장사 공시: {total}건",
    ]
    for cls in sorted(by_cls):
        label = cls_label.get(cls, cls)
        lines.append(f"  • {label}: {by_cls[cls]}건")
    return "\n".join(lines)


def format_dart_new_disclosure(d: dict) -> str:
    """Format a single new DART disclosure notification.

    Args:
        d: Disclosure record from list_dart_disclosures_by_date.

    Returns:
        HTML-formatted Telegram message.
    """
    cls_label = {"유": "유가증권", "코": "코스닥"}
    corp_cls = d.get("corp_cls", "")
    cls_kr = cls_label.get(corp_cls, corp_cls)
    rcept_dt = d.get("rcept_dt")
    time_str = rcept_dt.strftime("%H:%M") if hasattr(rcept_dt, "strftime") else ""
    return "\n".join(
        [
            "📋 <b>새 공시</b>",
            "",
            f"[{cls_kr}] {d.get('corp_name', '')}",
            f"{d.get('report_nm', '')}",
            f"제출: {d.get('flr_nm', '')} | {time_str}",
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


def format_deviation_summary(entries: list[dict], threshold: float, label: str = "장 마감") -> str:
    """Format a deviation ratio summary for all tracked items.

    Args:
        entries: List of dicts with keys: code, name, current, ma50, ratio.
        threshold: Alert threshold; entries at or above this are highlighted.
        label: Context label shown in the header (e.g. '장 마감', '장 시작').

    Returns:
        HTML-formatted Telegram message.
    """
    lines = [f"📊 <b>이격도 일일 요약 ({label})</b>", ""]
    for e in entries:
        ratio = e["ratio"]
        if ratio >= threshold:
            lines.append(f"⚠️ {e['name']} ({e['code']}): <b>{ratio:.1f}</b>")
        else:
            lines.append(f"• {e['name']} ({e['code']}): {ratio:.1f}")
    return "\n".join(lines)


def format_adr_summary(entries: list[dict], overbought: float, oversold: float, label: str = "장 마감") -> str:
    """Format an ADR (advance-decline ratio) summary for the market indices.

    Args:
        entries: List of dicts with keys: code, name, adr.
        overbought: ADR at or above this is flagged 과열 (overbought).
        oversold: ADR at or below this is flagged 바닥 (oversold).
        label: Context label shown in the header (e.g. '장 마감', '장 시작').

    Returns:
        HTML-formatted Telegram message.
    """
    lines = [f"📈 <b>ADR 일일 요약 ({label})</b>", ""]
    for e in entries:
        adr = e["adr"]
        if adr >= overbought:
            lines.append(f"⚠️ {e['name']} ({e['code']}): <b>{adr:.1f}</b> (과열)")
        elif adr <= oversold:
            lines.append(f"🔻 {e['name']} ({e['code']}): <b>{adr:.1f}</b> (바닥)")
        else:
            lines.append(f"• {e['name']} ({e['code']}): {adr:.1f}")
    return "\n".join(lines)
