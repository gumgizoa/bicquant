import logging
import os

from langchain_anthropic import ChatAnthropic
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

llm = ChatAnthropic(model="claude-sonnet-4-6")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "BicQuant bot is running. /ask {질문} 으로 질문하세요."
    )


async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("사용법: /ask {질문}")
        return

    # user_input = " ".join(context.args)
    await update.message.reply_text("생각 중...")

    # response = llm.invoke([HumanMessage(content=user_input)])
    response = "LLM 답변으로 대체될 예정입니다. 테스트 중..."
    await update.message.reply_text(response.content)


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ask", ask))
    app.run_polling()


if __name__ == "__main__":
    main()
