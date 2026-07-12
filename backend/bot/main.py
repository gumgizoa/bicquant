import asyncio
import datetime
import logging
import re
import zoneinfo

from dotenv import load_dotenv
from fredapi import Fred
from langchain_core.messages import HumanMessage
from langchain_openai.chat_models import AzureChatOpenAI
from shared import db
from shared.config import get_config
from shared.queries import watchlist as watchlist_q
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

from bot.features.macro_report import MacroPoint, format_macro_report
from bot.features.market_report import adr_from_rows, deviation_ratio, format_market_report
from bot.features.mdd import max_drawdown
from bot.features.watchlist_report import format_watchlist_report
from kofiaapi import CreditBalance, KofiaClient
from lsapi import AsyncLSClient as LSClient

load_dotenv()

_cfg = get_config("bot")

logging.basicConfig(level=getattr(logging, _cfg.log_level, logging.INFO))

# Group chat allowed to interact with this bot.
# Set TELEGRAM_CHAT_GROUP_ID in .env (different value per environment).
ALLOWED_CHAT_IDS: frozenset[int] = frozenset({int(_cfg.telegram.chat_group_id)})


def _allowed(update: Update) -> bool:
    return update.effective_chat is not None and update.effective_chat.id in ALLOWED_CHAT_IDS


llm = AzureChatOpenAI(
    model=_cfg.azure_openai.model,
    openai_api_key=_cfg.azure_openai.api_key,
    openai_api_version=_cfg.azure_openai.api_version,
    azure_endpoint=_cfg.azure_openai.endpoint,
    azure_deployment=_cfg.azure_openai.deployment,
)

_ls_client: LSClient | None = None


def _get_ls_client() -> LSClient:
    global _ls_client
    if _ls_client is None:
        _ls_client = LSClient(
            app_key=_cfg.ls_api.app_key,
            app_secret=_cfg.ls_api.app_secret,
        )
    return _ls_client


_KST = zoneinfo.ZoneInfo("Asia/Seoul")
# JobQueue.run_daily days: 0=Sun … 6=Sat (telegram.ext.JobQueue._CRON_MAPPING)
_WEEKDAYS = (1, 2, 3, 4, 5)

# 시장 요약 대상 지수 (KOSPI=001, KOSDAQ=301)
_INDICES = [("001", "코스피"), ("301", "코스닥")]

# KOFIA 신용공여 잔고 조회 구간 (일). 연휴를 감안해 최근 2영업일 행을 확보할 만큼 넉넉히.
_CREDIT_LOOKBACK_DAYS = 14

# FRED 조회 구간 (일). 일별 계열은 최근 2관측치만 있으면 되고, 월별 계열은 YoY까지 보려면
# 13개월치가 필요하다 (발표 지연 + 결측을 감안해 넉넉히 잡는다).
_FRED_DAILY_LOOKBACK_DAYS = 30
_FRED_MONTHLY_LOOKBACK_DAYS = 600

_kofia_client = KofiaClient()
_fred_client = Fred(api_key=_cfg.fred.api_key)


def _is_kr_code(ticker: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", ticker))


def _sign_parts(sign: str) -> tuple[str, str]:
    if sign in ("1", "2"):
        return "+", "▲"
    if sign in ("4", "5"):
        return "-", "▼"
    return "", "━"


async def _fetch_kr_stock(shcode: str) -> str:
    client = _get_ls_client()
    resp = await client.call("t1101", shcode=shcode)
    d = resp.block("t1101OutBlock") or {}

    name = d.get("hname", shcode)
    price = int(float(d.get("price") or 0))
    sign = str(d.get("sign", "3"))
    change = int(float(d.get("change") or 0))
    diff_pct = float(d.get("diff") or 0)
    volume = int(float(d.get("volume") or 0))
    high = int(float(d.get("high") or 0))
    low = int(float(d.get("low") or 0))

    cs, arrow = _sign_parts(sign)
    if sign in ("4", "5"):
        diff_pct = -abs(diff_pct)

    return (
        f"{name} ({shcode}) 🇰🇷\n"
        f"현재가: ₩{price:,} {arrow} {cs}{diff_pct:.2f}% (₩{cs}{change:,})\n"
        f"고가: ₩{high:,} / 저가: ₩{low:,}\n"
        f"거래량: {volume:,}"
    )


async def _fetch_us_stock(symbol: str) -> str:
    client = _get_ls_client()
    for exchcd in ("82", "81"):  # 82=NASDAQ, 81=NYSE/AMEX
        try:
            resp = await client.call(
                "g3101",
                {
                    "g3101InBlock": {
                        "delaygb": "R",
                        "keysymbol": f"{exchcd}{symbol}",
                        "exchcd": exchcd,
                        "symbol": symbol,
                    }
                },
            )
            d = resp.block("g3101OutBlock") or {}
            if not d.get("symbol") or not d.get("price"):
                continue

            floatpoint = int(d.get("floatpoint") or 2)
            fmt = f",.{floatpoint}f"
            price = float(d.get("price") or 0)
            sign = str(d.get("sign", "3"))
            diff = float(d.get("diff") or 0)
            rate = float(d.get("rate") or 0)
            volume = int(float(d.get("volume") or 0))
            high52 = float(d.get("high52p") or 0)
            low52 = float(d.get("low52p") or 0)
            name = d.get("korname") or symbol
            exch_name = {"82": "NASDAQ", "81": "NYSE"}.get(exchcd, exchcd)

            cs, arrow = _sign_parts(sign)
            if sign in ("4", "5"):
                rate = -abs(rate)

            return (
                f"{name} ({symbol}/{exch_name}) 🇺🇸\n"
                f"현재가: ${price:{fmt}} {arrow} {cs}{rate:.2f}% (${cs}{diff:{fmt}})\n"
                f"52주 고가: ${high52:{fmt}} / 저가: ${low52:{fmt}}\n"
                f"거래량: {volume:,}"
            )
        except Exception:
            continue
    raise ValueError(f"'{symbol}' 데이터를 가져올 수 없습니다.")


async def _fetch_kr_daily_closes(shcode: str, count: int) -> list[tuple[str, float]]:
    """(date, close) daily bars for a KR stock, oldest first, via t8451."""
    client = _get_ls_client()
    resp = await client.call(
        "t8451",
        {
            "t8451InBlock": {
                "shcode": shcode,
                "gubun": "2",  # daily bars
                "qrycnt": count,
                "sdate": "",
                "edate": "99999999",
                "cts_date": "",
                "comp_yn": "N",
                "sujung": "1",  # adjusted price
                "exchgubun": "K",
            }
        },
    )
    rows = resp.block("t8451OutBlock1") or []
    rows = sorted(rows, key=lambda r: r.get("date", ""))
    return [(r["date"], float(r["close"])) for r in rows if str(r.get("close", "")).strip()]


async def _fetch_us_daily_closes(symbol: str, count: int) -> list[tuple[str, float]]:
    """(date, close) daily bars for a US stock, oldest first, via g3103.

    g3103 returns rows newest-first, so they are re-sorted ascending by date.
    ``count`` is accepted for symmetry with the KR fetcher; g3103 has no query
    count and returns a fixed recent window.
    """
    client = _get_ls_client()
    for exchcd in ("82", "81"):  # 82=NASDAQ, 81=NYSE/AMEX
        try:
            resp = await client.call(
                "g3103",
                {
                    "g3103InBlock": {
                        "delaygb": "R",
                        "keysymbol": f"{exchcd}{symbol}",
                        "exchcd": exchcd,
                        "symbol": symbol,
                        "gubun": "2",  # daily bars
                        "date": "",
                    }
                },
            )
            rows = resp.block("g3103OutBlock1") or []
            if not rows:
                continue
            rows = sorted(rows, key=lambda r: r.get("chedate", ""))
            return [(r["chedate"], float(r["price"])) for r in rows if str(r.get("price", "")).strip()]
        except Exception:
            continue
    raise ValueError(f"'{symbol}' 데이터를 가져올 수 없습니다.")


def _recent_range(days: int = 30) -> tuple[str, str]:
    """(sdate, edate) as YYYYMMDD covering the last `days` calendar days (KST)."""
    today = datetime.datetime.now(_KST).date()
    return (today - datetime.timedelta(days=days)).strftime("%Y%m%d"), today.strftime("%Y%m%d")


async def _fetch_credit_info(shcode: str) -> dict | None:
    """t1926 — 종목별신용정보 (융자/대주 잔고). KR only; None on failure."""
    try:
        resp = await _get_ls_client().call("t1926", {"t1926InBlock": {"shcode": shcode}})
        return resp.block("t1926OutBlock") or None
    except Exception as e:
        logging.warning(f"t1926 (credit) failed for {shcode}: {e}")
        return None


async def _fetch_short_daily(shcode: str) -> dict | None:
    """t1927 — 공매도일별추이. Latest row (rows are newest-first). KR only."""
    sdate, edate = _recent_range()
    try:
        resp = await _get_ls_client().call(
            "t1927",
            {"t1927InBlock": {"shcode": shcode, "date": "", "sdate": sdate, "edate": edate}},
        )
        rows = resp.block("t1927OutBlock1") or []
        return rows[0] if rows else None
    except Exception as e:
        logging.warning(f"t1927 (short) failed for {shcode}: {e}")
        return None


async def _fetch_lending_daily(shcode: str) -> dict | None:
    """t1941 — 종목별대차거래일간추이. Latest row (newest-first). KR only."""
    sdate, edate = _recent_range()
    try:
        resp = await _get_ls_client().call(
            "t1941",
            {"t1941InBlock": {"shcode": shcode, "sdate": sdate, "edate": edate}},
        )
        rows = resp.block("t1941OutBlock1") or []
        return rows[0] if rows else None
    except Exception as e:
        logging.warning(f"t1941 (lending) failed for {shcode}: {e}")
        return None


async def _call_retry_ratelimit(tr: str, payload: dict):
    """LS TR 호출. 게이트웨이 초당 호출 제한(IGW00201)에 걸리면 한 번만 재시도한다."""
    for attempt in range(2):
        try:
            return await _get_ls_client().call(tr, payload)
        except Exception as e:
            if attempt == 0 and "IGW00201" in str(e):
                logging.warning(f"{tr} rate-limited (IGW00201); retrying in 3s")
                await asyncio.sleep(3)
                continue
            raise


async def _fetch_index_closes(upcode: str, count: int = 60) -> list[float]:
    """t8429 — 업종 일봉. 지수 종가를 오래된 것부터 반환."""
    resp = await _call_retry_ratelimit(
        "t8429",
        {
            "t8429InBlock": {
                "shcode": upcode,
                "gubun": "2",  # daily bars (spec: 2=일, 3=주, 4=월)
                "qrycnt": count,
                "sdate": "",
                "edate": "99999999",
                "cts_date": "",
                "comp_yn": "N",
            }
        },
    )
    return [float(r["close"]) for r in (resp.block("t8429OutBlock1") or []) if r.get("close")]


async def _fetch_adr(upcode: str, period: int) -> float | None:
    """t1514 — 업종기간별추이를 받아 ADR(등락비율)을 계산."""
    resp = await _call_retry_ratelimit(
        "t1514",
        {
            "t1514InBlock": {
                "upcode": upcode,
                "gubun1": "",  # unused per spec
                "gubun2": "1",  # daily bars (spec: 1=일, 2=주, 3=월)
                "cts_date": "",
                "cnt": period,
                "rate_gbn": "",
            }
        },
    )
    return adr_from_rows(resp.block("t1514OutBlock1") or [], period)


async def _resolve_name(code: str) -> str | None:
    """Best-effort stock name lookup for watchlist labelling. KR only."""
    if not _is_kr_code(code):
        return None
    try:
        resp = await _get_ls_client().call("t1101", shcode=code)
        return (resp.block("t1101OutBlock") or {}).get("hname")
    except Exception:
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return
    await update.message.reply_text(
        "BicQuant 봇이 실행 중이에요.\n\n"
        "/stock {티커}   — 주가 조회\n"
        "/market         — 시장 요약 (이격도 + ADR + 신용공여 잔고 + 거시 지표)\n"
        "/mdd {티커} {기간} — 최대낙폭(MDD) 조회\n"
        "/report         — 관심종목 리포트 즉시 조회\n"
        "/watch {코드}   — 관심종목 추가\n"
        "/unwatch {코드} — 관심종목 삭제\n"
        "/watchlist      — 관심종목 목록\n"
        "/ask {질문}     — LLM에 질문"
    )


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return

    if not context.args:
        await update.message.reply_text("사용법: /ask {질문}")
        return

    user_input = " ".join(context.args)
    try:
        response = llm.invoke([HumanMessage(content=user_input)])
        await update.message.reply_text(response.content)
    except Exception as e:
        logging.error(f"[ask] LLM error: {e}")
        await update.message.reply_text(f"Error while invoking LLM: {e}")


async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return

    if not context.args:
        await update.message.reply_text("사용법: /stock {티커} (예: /stock 005930 또는 /stock AAPL)")
        return

    ticker = context.args[0].upper()
    try:
        if _is_kr_code(ticker):
            reply = await _fetch_kr_stock(ticker)
        else:
            reply = await _fetch_us_stock(ticker)
        await update.message.reply_text(reply)
    except Exception as e:
        logging.error(f"stock error for {ticker}: {e}")
        await update.message.reply_text(f"Failed to fetch data for '{ticker}'.")


def _fmt_date(yyyymmdd: str) -> str:
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}" if len(yyyymmdd) == 8 else yyyymmdd


async def mdd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return

    if len(context.args) < 2:
        await update.message.reply_text("사용법: /mdd {티커} {기간(거래일)} (예: /mdd 005930 60 또는 /mdd AAPL 120)")
        return

    ticker = context.args[0].upper()
    try:
        period = int(context.args[1])
        if period < 2:
            raise ValueError
    except ValueError:
        await update.message.reply_text("기간은 2 이상의 정수(거래일 수)여야 해요.")
        return
    period = min(period, 500)  # t8451 qrycnt cap

    is_kr = _is_kr_code(ticker)
    try:
        if is_kr:
            series = await _fetch_kr_daily_closes(ticker, period)
        else:
            series = await _fetch_us_daily_closes(ticker, period)
    except Exception as e:
        logging.error(f"mdd fetch error for {ticker}: {e}")
        await update.message.reply_text(f"'{ticker}' 데이터를 가져올 수 없어요.")
        return

    series = series[-period:]  # most recent `period` bars
    if len(series) < 2:
        await update.message.reply_text(f"'{ticker}' 가격 데이터가 부족해요 ({len(series)}일).")
        return

    dates = [d for d, _ in series]
    closes = [c for _, c in series]
    res = max_drawdown(closes)

    if is_kr:
        name = await _resolve_name(ticker)
        label = f"{name} ({ticker})" if name else ticker
        flag, cur, fmt = "🇰🇷", "₩", ",.0f"
    else:
        label, flag, cur, fmt = ticker, "🇺🇸", "$", ",.2f"

    await update.message.reply_text(
        f"📉 <b>MDD — {label}</b> {flag}\n"
        f"기간: 최근 {len(series)} 거래일 ({_fmt_date(dates[0])} ~ {_fmt_date(dates[-1])})\n"
        f"최대낙폭: <b>{res.mdd_pct:.2f}%</b>\n"
        f"고점: {cur}{closes[res.peak_idx]:{fmt}} ({_fmt_date(dates[res.peak_idx])})\n"
        f"저점: {cur}{closes[res.trough_idx]:{fmt}} ({_fmt_date(dates[res.trough_idx])})",
        parse_mode="HTML",
    )


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return

    if not context.args:
        await update.message.reply_text("사용법: /watch {코드} (예: /watch 005930 또는 /watch AAPL)")
        return

    code = context.args[0].upper()
    name = await _resolve_name(code)

    await watchlist_q.add(code, name)

    label = f"{name} ({code})" if name else code
    flag = "🇰🇷" if _is_kr_code(code) else "🇺🇸"
    await update.message.reply_text(f"✅ {label} {flag} 관심종목에 추가됐어요.")


async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return

    if not context.args:
        await update.message.reply_text("사용법: /unwatch {코드}")
        return

    code = context.args[0].upper()
    removed = await watchlist_q.remove(code)

    if removed:
        await update.message.reply_text(f"🗑 {code} 관심종목에서 삭제됐어요.")
    else:
        await update.message.reply_text(f"⚠️ {code} 는 관심종목에 없어요.")


async def watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        return

    items = await watchlist_q.get_active_items()

    if not items:
        await update.message.reply_text("관심종목이 없어요. /watch {code} 로 추가해보세요.")
        return

    lines = [f"📋 <b>관심종목</b> ({len(items)})"]
    for row in items:
        code = row.code
        name = row.name
        flag = "🇰🇷" if _is_kr_code(code) else "🇺🇸"
        label = f"{name} ({code})" if name else code
        lines.append(f"• {label} {flag}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ── 시장 요약 리포트 (지수 이격도 + ADR + 시장 신용공여 잔고) ──────────────────


async def _fetch_market_credit() -> tuple[CreditBalance, CreditBalance | None] | None:
    """KOFIA 시장 신용공여 잔고 — (최신, 직전 영업일) 쌍. 실패하면 ``None``.

    KofiaClient는 requests 기반 동기 클라이언트라 이벤트 루프를 막지 않게 스레드로 넘긴다.
    결제 기준이라 최신 행이 1영업일 정도 과거다 — 조회 구간을 넉넉히 잡아 최근 2행을 취한다.
    """
    end = datetime.datetime.now(_KST).date()
    start = end - datetime.timedelta(days=_CREDIT_LOOKBACK_DAYS)
    try:
        rows = await asyncio.to_thread(_kofia_client.credit_balance, start, end)
    except Exception as e:
        logging.warning(f"KOFIA credit balance fetch failed: {e}")
        return None

    if not rows:
        logging.warning("KOFIA credit balance: no rows in the last %d days", _CREDIT_LOOKBACK_DAYS)
        return None
    return rows[0], (rows[1] if len(rows) > 1 else None)  # rows are newest-first


async def _build_market_entries() -> tuple[list[dict], list[dict]]:
    """지수별 이격도 엔트리와 ADR 엔트리를 모은다. 데이터가 부족한 지수는 조용히 빠진다."""
    index_entries: list[dict] = []
    adr_entries: list[dict] = []

    for upcode, name in _INDICES:
        closes = await _fetch_index_closes(upcode)
        ratio = deviation_ratio(closes)
        if ratio is not None:
            index_entries.append({"code": upcode, "name": name, "current": closes[-1], "ma50": sum(closes[-51:-1]) / 50, "ratio": ratio})

    for upcode, name in _INDICES:
        adr = await _fetch_adr(upcode, int(_cfg.adr.period))
        if adr is not None:
            adr_entries.append({"code": upcode, "name": name, "adr": adr})

    return index_entries, adr_entries


async def _send_market_report(bot, label: str | None, *, include_credit: bool) -> None:
    """시장 요약(+ 해외 거시 지표)을 한 메시지로 그룹방에 발송.

    이격도/ADR/신용공여 잔고/거시 지표는 각각 자기 헤더를 가진 블록으로, 하나의 메시지에
    이어 붙는다. 어느 한 블록의 데이터가 없으면 그 블록만 빠지고, 전부 없으면 발송하지 않는다.

    신용공여 잔고는 장중 불변 + 1영업일 지연이라 장 시작에는 빼고 장 마감에만 붙인다
    (``include_credit``).
    """
    index_entries, adr_entries = await _build_market_entries()
    credit = await _fetch_market_credit() if include_credit else None
    market_msg = format_market_report(
        index_entries,
        adr_entries,
        dev_threshold=float(_cfg.deviation.threshold),
        adr_overbought=float(_cfg.adr.overbought),
        adr_oversold=float(_cfg.adr.oversold),
        credit=credit,
        label=label,
    )
    macro_msg = await _build_macro_block(label)

    blocks = [b for b in (market_msg, macro_msg) if b]
    if not blocks:
        logging.warning(f"market report ({label or '수동 조회'}): no data available")
        return
    await bot.send_message(chat_id=_cfg.telegram.chat_group_id, text="\n\n".join(blocks), parse_mode="HTML")


async def market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """On-demand 시장 요약 (이격도 + ADR + 신용공여 잔고 + 거시 지표), no label tag."""
    if not _allowed(update):
        return
    try:
        await _send_market_report(context.bot, None, include_credit=True)
    except Exception as e:
        logging.error(f"[market] failed: {e}")
        await update.message.reply_text(f"시장 요약 생성에 실패했어요: {e}")


# ── 해외 거시 지표 (미 국채 10년물 + 미국 M2) — 시장 요약 메시지의 한 블록 ──────


def _fred_point(series_id: str, *, monthly: bool) -> MacroPoint | None:
    """FRED 시계열의 최신 관측치를 ``MacroPoint``로. 데이터가 없으면 ``None``.

    DGS10은 휴장일에 NaN 행이 들어오므로 결측을 먼저 털어낸다. 월별 계열은 연속적이라
    12칸 앞(``[-13]``)이 곧 1년 전 값이다 — 없으면 YoY 없이 나간다.
    """
    lookback = _FRED_MONTHLY_LOOKBACK_DAYS if monthly else _FRED_DAILY_LOOKBACK_DAYS
    start = datetime.datetime.now(_KST).date() - datetime.timedelta(days=lookback)
    series = _fred_client.get_series(series_id, observation_start=start).dropna()
    if series.empty:
        return None
    return MacroPoint(
        date=series.index[-1].date(),
        value=float(series.iloc[-1]),
        prev=float(series.iloc[-2]) if len(series) > 1 else None,
        year_ago=float(series.iloc[-13]) if monthly and len(series) >= 13 else None,
    )


async def _fetch_macro_point(series_id: str, *, monthly: bool) -> MacroPoint | None:
    """FRED 관측치 하나. 실패하면 로그만 남기고 ``None`` — 다른 지표는 계속 나가야 한다.

    fredapi는 requests 기반 동기 클라이언트라 이벤트 루프를 막지 않게 스레드로 넘긴다.
    """
    try:
        return await asyncio.to_thread(_fred_point, series_id, monthly=monthly)
    except Exception as e:
        logging.warning(f"FRED fetch failed for {series_id}: {e}")
        return None


async def _build_macro_block(label: str | None) -> str | None:
    """시장 요약 메시지에 붙일 거시 지표 블록. 데이터가 없으면 ``None`` (블록만 빠진다).

    M2는 월별이라 장 시작/마감 사이에 값이 변하지 않지만, 기준월과 MoM/YoY를 함께 보여주므로
    두 리포트에 모두 싣는다 (신용공여 잔고와 달리 ``include_credit`` 같은 분기가 없다).
    """
    treasury = await _fetch_macro_point(_cfg.macro.treasury_series, monthly=False)
    m2_us = await _fetch_macro_point(_cfg.macro.m2_us_series, monthly=True)
    block = format_macro_report(
        treasury,
        m2_us,
        treasury_move_alert=float(_cfg.macro.treasury_move_alert),
        label=label,
    )
    if block is None:
        logging.warning(f"macro block ({label or '수동 조회'}): no data available")
    return block


# ── 관심종목 일일 리포트 ────────────────────────────────────────────────────────


async def _build_watchlist_entries(include_credit: bool) -> list[dict]:
    """Collect per-stock metrics for every active watchlist code.

    KR stocks get 이격도 + MDD (+ 신용/공매도/대차 when ``include_credit``).
    US stocks only get MDD — g3103 returns too few bars for MA50, and the credit
    /short/lending TRs are KR-only.
    """
    mdd_period = int(_cfg.mdd.period)
    entries: list[dict] = []

    for code in await watchlist_q.get_active_codes():
        is_kr = _is_kr_code(code)
        entry: dict = {"code": code, "name": code, "is_kr": is_kr}

        try:
            if is_kr:
                entry["name"] = await _resolve_name(code) or code
                series = await _fetch_kr_daily_closes(code, max(60, mdd_period))
            else:
                series = await _fetch_us_daily_closes(code, mdd_period)
        except Exception as e:
            logging.warning(f"watchlist report: price fetch failed for {code}: {e}")
            series = []

        closes = [c for _, c in series]
        if len(closes) >= 51:
            ma50 = sum(closes[-51:-1]) / 50
            if ma50 > 0:
                entry["ratio"] = closes[-1] / ma50 * 100
        if len(closes) >= 2:
            window = closes[-mdd_period:]
            entry["mdd"] = max_drawdown(window).mdd_pct
            entry["mdd_days"] = len(window)

        if include_credit and is_kr:
            entry["credit"] = await _fetch_credit_info(code)
            entry["short"] = await _fetch_short_daily(code)
            entry["lending"] = await _fetch_lending_daily(code)

        entries.append(entry)

    return entries


async def _send_watchlist_report(bot, label: str | None, *, include_credit: bool) -> None:
    entries = await _build_watchlist_entries(include_credit)
    msg = format_watchlist_report(
        entries,
        dev_threshold=float(_cfg.deviation.threshold),
        mdd_alert=float(_cfg.mdd.alert_threshold),
        label=label,
    )
    await bot.send_message(chat_id=_cfg.telegram.chat_group_id, text=msg, parse_mode="HTML")


async def _job_market_open(context: ContextTypes.DEFAULT_TYPE) -> None:
    """장 시작 — 시장 요약과 관심종목 리포트를 각각 별도 메시지로 발송.

    신용 관련 지표는 모두 빠진다: 시장 신용공여 잔고(KOFIA)도, 관심종목의 신용/공매도/대차도
    일별 결제 기준이라 장중에 변하지 않는다. 장 마감 리포트에만 붙인다.
    한쪽이 실패해도 다른 쪽은 나가야 하므로 개별적으로 잡아 로그를 남긴다.
    """
    await _send_daily_reports(context.bot, "장 시작", include_credit=False)


async def _job_market_close(context: ContextTypes.DEFAULT_TYPE) -> None:
    """장 마감 — 시장 요약(+ 시장 신용공여 잔고) + 관심종목 리포트(+ 신용/공매도/대차)."""
    await _send_daily_reports(context.bot, "장 마감", include_credit=True)


async def _send_daily_reports(bot, label: str, *, include_credit: bool) -> None:
    try:
        await _send_market_report(bot, label, include_credit=include_credit)
    except Exception as e:
        logging.error(f"[{label}] market report failed: {e}")

    try:
        await _send_watchlist_report(bot, label, include_credit=include_credit)
    except Exception as e:
        logging.error(f"[{label}] watchlist report failed: {e}")


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """On-demand full report (이격도 + MDD + 신용/공매도/대차), no label tag."""
    if not _allowed(update):
        return
    try:
        await _send_watchlist_report(context.bot, None, include_credit=True)
    except Exception as e:
        logging.error(f"[report] failed: {e}")
        await update.message.reply_text(f"리포트 생성에 실패했어요: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram.error import Conflict

    if isinstance(context.error, Conflict):
        logging.warning("Conflict: another bot instance is running. Retrying...")
        return
    logging.error("Unhandled exception", exc_info=context.error)


# ── DB lifecycle ──────────────────────────────────────────────────────────────


async def _post_init(app: Application) -> None:
    await db.init()


async def _post_shutdown(app: Application) -> None:
    await db.close()


def _hhmm(value: str) -> datetime.time:
    """'09:00' → time(9, 0, tzinfo=KST)."""
    hour, minute = str(value).split(":")
    return datetime.time(int(hour), int(minute), tzinfo=_KST)


def main() -> None:
    token = _cfg.telegram.bot_token
    app = ApplicationBuilder().token(token).post_init(_post_init).post_shutdown(_post_shutdown).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ask", ask))
    app.add_handler(CommandHandler("stock", stock))
    app.add_handler(CommandHandler("mdd", mdd))
    app.add_handler(CommandHandler("market", market))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("unwatch", unwatch))
    app.add_handler(CommandHandler("watchlist", watchlist))
    app.add_error_handler(error_handler)

    # 일일 리포트 (시장 요약 + 관심종목, 각각 별도 메시지) — 평일 장 시작 / 장 마감 (KST)
    app.job_queue.run_daily(_job_market_open, time=_hhmm(_cfg.daily_report.open_time), days=_WEEKDAYS, name="daily_open")
    app.job_queue.run_daily(_job_market_close, time=_hhmm(_cfg.daily_report.close_time), days=_WEEKDAYS, name="daily_close")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
