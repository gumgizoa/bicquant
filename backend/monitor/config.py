import os

LS_APP_KEY = os.environ["LS_OPENAPI_APP_KEY"]
LS_APP_SECRET = os.environ["LS_OPENAPI_APP_SECRET"]

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
# Group chat ID to send alerts to (separate from bot command chat if needed)
TELEGRAM_ALERT_CHAT_ID = os.environ["MONITOR_TELEGRAM_CHAT_ID"]

DATABASE_URL = os.environ["DATABASE_URL"]

# Comma-separated KRX stock codes to include in deviation monitoring (e.g. "005930,000660")
STOCK_CODES: list[str] = [s.strip() for s in os.getenv("MONITOR_STOCK_CODES", "").split(",") if s.strip()]

DEVIATION_THRESHOLD = float(os.getenv("DEVIATION_THRESHOLD", "130"))
# Seconds between deviation polls during market hours
DEVIATION_POLL_INTERVAL = int(os.getenv("DEVIATION_POLL_INTERVAL", "600"))

AZURE_OPENAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
AZURE_OPENAI_API_VERSION = os.environ["AZURE_OPENAI_API_VERSION"]
AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
AZURE_OPENAI_DEPLOYMENT = os.environ["AZURE_OPENAI_DEPLOYMENT"]
