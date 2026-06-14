"""Live tests for the generated wrappers and the stock convenience layer."""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()
HAVE_CREDS = bool(os.environ.get("LS_OPENAPI_APP_KEY") and os.environ.get("LS_OPENAPI_APP_SECRET"))
SHCODE = "005930"

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not HAVE_CREDS, reason="LS creds not set")]


def test_generated_wrapper_t1101(live_client) -> None:
    resp = live_client.api.stock_quote.t1101(shcode=SHCODE)
    assert resp.ok
    assert resp.block("t1101OutBlock")["hname"]


def test_generated_wrapper_t1102(live_client) -> None:
    resp = live_client.api.stock_quote.t1102(shcode=SHCODE)
    assert resp.ok
    assert int(resp.block("t1102OutBlock")["price"]) > 0


def test_stock_convenience_quote(live_client) -> None:
    resp = live_client.stock.quote(SHCODE)
    assert resp.ok
    assert resp.block("t1101OutBlock")["hname"]


def test_stock_daily_chart_returns_rows(live_client) -> None:
    resp = live_client.stock.daily_chart(SHCODE, qrycnt=5)
    assert resp.ok
    rows = resp.block("t8410OutBlock1")
    assert isinstance(rows, list) and rows
    assert int(rows[-1]["close"]) > 0
