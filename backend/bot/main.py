import datetime
import logging
import re
import zoneinfo

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai.chat_models import AzureChatOpenAI
from shared import db
from shared.config import get_config
from shared.queries import watchlist as watchlist_q
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

from bot.features.mdd import max_drawdown
from bot.features.watchlist_report import format_watchlist_report
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


async def _send_watchlist_report(bot, label: str, *, include_credit: bool) -> None:
    entries = await _build_watchlist_entries(include_credit)
    msg = format_watchlist_report(
        entries,
        dev_threshold=float(_cfg.deviation.threshold),
        mdd_alert=float(_cfg.mdd.alert_threshold),
        label=label,
    )
    await bot.send_message(chat_id=_cfg.telegram.chat_group_id, text=msg, parse_mode="HTML")


async def _job_market_open(context: ContextTypes.DEFAULT_TYPE) -> None:
    """장 시작 — 이격도 + MDD (신용/공매도/대차는 일별 데이터라 제외)."""
    await _send_watchlist_report(context.bot, "장 시작", include_credit=False)


async def _job_market_close(context: ContextTypes.DEFAULT_TYPE) -> None:
    """장 마감 — 이격도 + MDD + 신용잔고/공매도/대차."""
    await _send_watchlist_report(context.bot, "장 마감", include_credit=True)


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """On-demand run of the 장 마감 report (full, incl. 신용/공매도/대차)."""
    if not _allowed(update):
        return
    await update.message.reply_text("관심종목 리포트를 만드는 중이에요…")
    try:
        await _send_watchlist_report(context.bot, "수동 조회", include_credit=True)
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
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("unwatch", unwatch))
    app.add_handler(CommandHandler("watchlist", watchlist))
    app.add_error_handler(error_handler)

    # 관심종목 리포트 — 평일 장 시작 / 장 마감 (KST)
    app.job_queue.run_daily(_job_market_open, time=_hhmm(_cfg.watchlist_report.open_time), days=_WEEKDAYS, name="watchlist_open")
    app.job_queue.run_daily(_job_market_close, time=_hhmm(_cfg.watchlist_report.close_time), days=_WEEKDAYS, name="watchlist_close")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
