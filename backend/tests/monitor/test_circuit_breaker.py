"""Tests for circuit-breaker handling in monitor.sidecar / monitor.notifier.

Live (``slow``) tests hit the real LS API, dev Postgres, and dev Telegram chat.
Pure-function tests (status map, alert formatting) run offline.
"""

import pytest
from monitor.notifier import CB_EVENT_NAME, format_circuit_breaker_alert
from monitor.sidecar import _CB_STATUS
from shared.models import CircuitBreakerEvent

# ---------------------------------------------------------------------------
# _CB_STATUS mapping
# ---------------------------------------------------------------------------


def test_cb_status_l1_triggered() -> None:
    assert _CB_STATUS["61"] == "cb_l1_triggered"


def test_cb_status_l1_released() -> None:
    assert _CB_STATUS["62"] == "cb_l1_released"


def test_cb_status_l1_simul_close() -> None:
    assert _CB_STATUS["63"] == "cb_l1_simul_close"


def test_cb_status_l2_triggered() -> None:
    assert _CB_STATUS["68"] == "cb_l2_triggered"


def test_cb_status_l3_triggered() -> None:
    assert _CB_STATUS["69"] == "cb_l3_triggered"


def test_cb_status_l2_released() -> None:
    assert _CB_STATUS["70"] == "cb_l2_released"


def test_cb_status_l2_simul_close() -> None:
    assert _CB_STATUS["71"] == "cb_l2_simul_close"


def test_cb_status_covers_all_expected_codes() -> None:
    assert set(_CB_STATUS.keys()) == {"61", "62", "63", "68", "69", "70", "71"}


def test_cb_status_values_are_strings() -> None:
    for code, event_type in _CB_STATUS.items():
        assert isinstance(event_type, str), f"jstatus {code} should map to a string"


# ---------------------------------------------------------------------------
# format_circuit_breaker_alert — pure function
# ---------------------------------------------------------------------------


def test_format_cb_l1_triggered_includes_market_and_event() -> None:
    alert = format_circuit_breaker_alert("kospi", "cb_l1_triggered", {})
    assert "코스피" in alert
    assert "서킷브레이크 1단계 발동" in alert


def test_format_cb_l2_triggered_includes_double_siren() -> None:
    alert = format_circuit_breaker_alert("kospi", "cb_l2_triggered", {})
    assert "🚨🚨" in alert


def test_format_cb_l3_triggered_mentions_market_close() -> None:
    alert = format_circuit_breaker_alert("kosdaq", "cb_l3_triggered", {})
    assert "당일 장종료" in alert
    assert "🔴" in alert


def test_format_cb_includes_index_info() -> None:
    info = {"current": "2,500.00", "change_pct": "-8.10"}
    alert = format_circuit_breaker_alert("kospi", "cb_l1_triggered", info)
    assert "2,500.00" in alert
    assert "-8.10" in alert


@pytest.mark.parametrize("event_type", list(CB_EVENT_NAME.keys()))
def test_format_all_cb_event_types_produce_output(event_type: str) -> None:
    alert = format_circuit_breaker_alert("kospi", event_type, {})
    assert len(alert) > 0


# ---------------------------------------------------------------------------
# Live: circuit-breaker event persistence — real dev DB round-trip
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_cb_save_event_roundtrip(live_db) -> None:
    from shared.queries import circuit_breaker as cb_q

    before = await live_db.max_id(CircuitBreakerEvent)
    try:
        raw = {"jangubun": "1", "jstatus": "61", "current": "2,500.00", "change_pct": "-8.10"}
        await cb_q.save_event("kospi", "cb_l1_triggered", "", raw)

        rows = await live_db.rows_after(CircuitBreakerEvent, before)
        assert len(rows) == 1
        row = rows[0]
        assert row.market == "kospi"
        assert row.event_type == "cb_l1_triggered"
        assert row.raw_data["jstatus"] == "61"
    finally:
        await live_db.delete_after(CircuitBreakerEvent, before)


# ---------------------------------------------------------------------------
# handle_jif — circuit-breaker dispatch (real module-level function).
#
# handle_jif() is now a module-level function taking the LS client explicitly,
# so the live tests drive the *real* routing/dispatch logic end-to-end (real LS
# snapshot, real DB persistence, real Telegram) instead of re-implementing it.
# The no-op routing guards return before any external call, so they run offline.
# ---------------------------------------------------------------------------


@pytest.mark.slow
async def test_handle_jif_cb_event_writes_cb_row(ls_client, live_db, telegram) -> None:
    from monitor.sidecar import handle_jif

    msg = {"body": {"jangubun": "1", "jstatus": "61"}}  # KOSPI, cb_l1_triggered
    before = await live_db.max_id(CircuitBreakerEvent)
    try:
        await handle_jif(ls_client, msg)

        rows = await live_db.rows_after(CircuitBreakerEvent, before)
        assert len(rows) == 1
        assert rows[0].market == "kospi"
        assert rows[0].event_type == "cb_l1_triggered"
        assert rows[0].raw_data["jstatus"] == "61"
    finally:
        await live_db.delete_after(CircuitBreakerEvent, before)


@pytest.mark.slow
async def test_handle_jif_cb_event_does_not_write_sidecar(ls_client, live_db, telegram) -> None:
    from monitor.sidecar import handle_jif
    from shared.models import SidecarEvent

    msg = {"body": {"jangubun": "2", "jstatus": "68"}}  # KOSDAQ, cb_l2_triggered
    cb_before = await live_db.max_id(CircuitBreakerEvent)
    sc_before = await live_db.max_id(SidecarEvent)
    try:
        await handle_jif(ls_client, msg)

        assert len(await live_db.rows_after(CircuitBreakerEvent, cb_before)) == 1
        assert await live_db.rows_after(SidecarEvent, sc_before) == []
    finally:
        await live_db.delete_after(CircuitBreakerEvent, cb_before)


async def test_handle_jif_unknown_jstatus_is_noop() -> None:
    # jstatus 99 matches neither map → returns before any external call.
    from monitor.sidecar import handle_jif

    await handle_jif(None, {"body": {"jangubun": "1", "jstatus": "99"}})


async def test_handle_jif_non_equity_market_is_noop() -> None:
    # jangubun 5 (futures) is not in _MARKET → returns immediately.
    from monitor.sidecar import handle_jif

    await handle_jif(None, {"body": {"jangubun": "5", "jstatus": "61"}})
