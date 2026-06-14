"""Live tests for the synchronous LSClient against the real LS OpenAPI.

Read-only TRs only — no orders are placed.
"""

import os
import time

import pytest
from dotenv import load_dotenv

from lsapi import LSApiError

load_dotenv()
HAVE_CREDS = bool(os.environ.get("LS_OPENAPI_APP_KEY") and os.environ.get("LS_OPENAPI_APP_SECRET"))
SHCODE = "005930"  # Samsung Electronics (KOSPI)

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not HAVE_CREDS, reason="LS creds not set")]


def test_call_kwargs_form_returns_quote(live_client) -> None:
    resp = live_client.call("t1101", shcode=SHCODE)
    assert resp.ok
    assert resp.rsp_cd == "00000"
    block = resp.block("t1101OutBlock")
    assert block and block.get("hname")  # Korean name present
    assert int(block["price"]) > 0


def test_call_body_form_matches_kwargs_form(live_client) -> None:
    resp = live_client.call("t1101", {"t1101InBlock": {"shcode": SHCODE}})
    assert resp.ok
    assert resp.block("t1101OutBlock")["hname"]


def test_sequential_calls_respect_per_tr_throttle(live_client) -> None:
    """Three back-to-back same-TR calls must honor the TR's TPS gap."""
    spec = live_client.catalog.tr("t1101")
    assert spec.tps_limit  # t1101 advertises a per-second quota
    gap = 1.0 / spec.tps_limit
    start = time.monotonic()
    for _ in range(3):
        assert live_client.call("t1101", shcode=SHCODE).ok
    elapsed = time.monotonic() - start
    assert elapsed >= 2 * gap  # 3 calls => at least 2 enforced gaps


def test_realtime_tr_rejected_on_rest(live_client) -> None:
    """Realtime TRs must be refused by the REST path (raised before any network)."""
    with pytest.raises(LSApiError):
        live_client.call("JIF")
