import logging
import os

import yfinance as yf
from langchain_core.messages import HumanMessage
from langchain_openai.chat_models import AzureChatOpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

# bicquant: -1003800004196, bicquant-dev: -5158136283
ALLOWED_CHAT_IDS = {-1003800004196, -5158136283}

if not os.getenv("AZURE_OPENAI_API_KEY"):
    raise RuntimeError("AZURE_OPENAI_API_KEY is not set or is empty in environment variables.")

llm = AzureChatOpenAI(
    model="gpt-5",
    openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id not in ALLOWED_CHAT_IDS:
        return
    await update.message.reply_text("BicQuant bot is running. Use /ask {question} to ask a question.")


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id not in ALLOWED_CHAT_IDS:
        return

    if not context.args:
        await update.message.reply_text("Usage: /ask {question}")
        return

    user_input = " ".join(context.args)
    try:
        response = llm.invoke([HumanMessage(content=user_input)])
        await update.message.reply_text(response.content)
    except Exception as e:
        logging.error(f"[ask] LLM error: {e}")
        await update.message.reply_text(f"Error while invoking LLM: {e}")


async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id not in ALLOWED_CHAT_IDS:
        return

    if not context.args:
        await update.message.reply_text("Usage: /stock {ticker} (e.g. /stock AAPL or /stock 005930.KS)")
        return

    ticker_symbol = context.args[0].upper()
    is_korean = ticker_symbol.endswith(".KS") or ticker_symbol.endswith(".KQ")
    currency = "₩" if is_korean else "$"
    flag = "🇰🇷" if is_korean else "🇺🇸"

    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info

        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        if current_price is None:
            await update.message.reply_text(f"Ticker '{ticker_symbol}' not found.")
            return

        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose", current_price)
        change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0
        week_high = info.get("fiftyTwoWeekHigh", 0)
        week_low = info.get("fiftyTwoWeekLow", 0)
        volume = info.get("volume") or info.get("regularMarketVolume", 0)

        change_sign = "+" if change_pct >= 0 else ""
        price_str = f"{currency}{int(current_price):,}" if is_korean else f"{currency}{current_price:,.2f}"
        high_str = f"{currency}{int(week_high):,}" if is_korean else f"{currency}{week_high:,.2f}"
        low_str = f"{currency}{int(week_low):,}" if is_korean else f"{currency}{week_low:,.2f}"

        reply = (
            f"{ticker_symbol} {flag}\nPrice: {price_str} ({change_sign}{change_pct:.2f}%)\n52w High: {high_str} / Low: {low_str}\nVolume: {volume:,}"
        )
        await update.message.reply_text(reply)

    except Exception as e:
        logging.error(f"stock error for {ticker_symbol}: {e}")
        await update.message.reply_text(f"Failed to fetch data for '{ticker_symbol}'.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram.error import Conflict

    if isinstance(context.error, Conflict):
        logging.warning("Conflict: another bot instance is running. Retrying...")
        return
    logging.error("Unhandled exception", exc_info=context.error)


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ask", ask))
    app.add_handler(CommandHandler("stock", stock))
    app.add_error_handler(error_handler)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
