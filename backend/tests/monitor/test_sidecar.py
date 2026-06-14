"""Tests for monitor.sidecar and sidecar alert formatting.

Live (``slow``) tests hit the real LS API and dev Postgres. Pure-function tests
(alert formatting, jstatus/market maps) run offline.
"""

import pytest
from monitor.notifier import format_sidecar_alert
from monitor.sidecar import _JSTATUS, _MARKET, _UPCODE, _fetch_index_snapshot
from shared.models import SidecarEvent

# ---------------------------------------------------------------------------
# format_sidecar_alert — pure function
# ---------------------------------------------------------------------------


def test_format_sell_triggered_includes_market_and_event() -> None:
    alert = format_sidecar_alert("kospi", "sell_triggered", {})
    assert "코스피" in alert
    assert "매도 사이드카 발동" in alert


def test_format_buy_triggered_includes_emoji() -> None:
    alert = format_sidecar_alert("kosdaq", "buy_triggered", {})
    assert "🚀" in alert


def test_format_includes_index_info() -> None:
    info = {"current": "2,700.00", "change_pct": "-3.50"}
    alert = format_sidecar_alert("kospi", "sell_triggered", info)
    assert "2,700.00" in alert
    assert "-3.50" in alert


@pytest.mark.parametrize("event_type", ["sell_triggered", "sell_released", "buy_triggered", "buy_released"])
def test_format_all_event_types_produce_output(event_type: str) -> None:
    alert = format_sidecar_alert("kospi", event_type, {})
    assert len(alert) > 0


# ---------------------------------------------------------------------------
# _JSTATUS / _MARKET — mapping correctness
# ---------------------------------------------------------------------------


def test_jstatus_sell_triggered() -> None:
    assert _JSTATUS["64"] == "sell_triggered"


def test_jstatus_sell_released() -> None:
    assert _JSTATUS["65"] == "sell_released"


def test_jstatus_buy_triggered() -> None:
    assert _JSTATUS["66"] == "buy_triggered"


def test_jstatus_buy_released() -> None:
    assert _JSTATUS["67"] == "buy_released"


def test_market_mapping() -> None:
    assert _MARKET["1"] == "kospi"
    assert _MARKET["2"] == "kosdaq"


# ---------------------------------------------------------------------------
# Live: _fetch_index_snapshot — real LS API
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("market", ["kospi", "kosdaq"])
async def test_fetch_index_snapshot_live(ls_client, market: str) -> None:
    info = await _fetch_index_snapshot(ls_client, _UPCODE[market])
    assert set(info) == {"current", "change_pct"}
    # current is a thousands-formatted positive number, e.g. "2,700.50"
    current = float(info["current"].replace(",", ""))
    assert current > 0
    # change_pct carries an explicit sign, e.g. "+0.42" / "-3.55"
    assert info["change_pct"][0] in "+-"


@pytest.mark.slow
async def test_fetch_index_snapshot_resilient_to_bad_upcode(ls_client) -> None:
    # The real gateway answers an unknown upcode with a zero-valued block rather
    # than an error, so the function returns a (zeroed) snapshot and never
    # raises. Either outcome — zeroed dict or empty dict — is acceptable; what
    # matters is that it does not propagate an exception to the caller.
    info = await _fetch_index_snapshot(ls_client, "ZZZ")
    assert isinstance(info, dict)
    assert set(info) in ({"current", "change_pct"}, set())


# ---------------------------------------------------------------------------
# Live: sidecar event persistence — real dev DB round-trip
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_sidecar_save_event_roundtrip(live_db) -> None:
    from shared.queries import sidecar as sidecar_q

    before = await live_db.max_id(SidecarEvent)
    try:
        raw = {"jangubun": "1", "jstatus": "64", "current": "2,700.00", "change_pct": "-3.50"}
        await sidecar_q.save_event("kospi", "sell_triggered", "", raw)

        rows = await live_db.rows_after(SidecarEvent, before)
        assert len(rows) == 1
        row = rows[0]
        assert row.market == "kospi"
        assert row.event_type == "sell_triggered"
        assert row.raw_data["jstatus"] == "64"
    finally:
        await live_db.delete_after(SidecarEvent, before)


# ---------------------------------------------------------------------------
# Live: handle_jif — sidecar dispatch (real module-level function)
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_handle_jif_sidecar_event_writes_sidecar_row(ls_client, live_db, telegram) -> None:
    from monitor.sidecar import handle_jif

    msg = {"body": {"jangubun": "1", "jstatus": "64"}}  # KOSPI, sell_triggered
    before = await live_db.max_id(SidecarEvent)
    try:
        await handle_jif(ls_client, msg)  # real LS snapshot + DB write + Telegram

        rows = await live_db.rows_after(SidecarEvent, before)
        assert len(rows) == 1
        assert rows[0].market == "kospi"
        assert rows[0].event_type == "sell_triggered"
        assert rows[0].raw_data["jstatus"] == "64"
    finally:
        await live_db.delete_after(SidecarEvent, before)
