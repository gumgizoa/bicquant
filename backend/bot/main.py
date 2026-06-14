import logging
import re

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai.chat_models import AzureChatOpenAI
from shared import db
from shared.config import get_config
from shared.queries import watchlist as watchlist_q
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

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


def main() -> None:
    token = _cfg.telegram.bot_token
    app = ApplicationBuilder().token(token).post_init(_post_init).post_shutdown(_post_shutdown).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ask", ask))
    app.add_handler(CommandHandler("stock", stock))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("unwatch", unwatch))
    app.add_handler(CommandHandler("watchlist", watchlist))
    app.add_error_handler(error_handler)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
