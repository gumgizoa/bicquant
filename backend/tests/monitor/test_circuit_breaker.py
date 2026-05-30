"""Unit tests for circuit breaker handling in monitor.sidecar and monitor.notifier."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from monitor.notifier import CB_EVENT_NAME, format_circuit_breaker_alert
from monitor.sidecar import _CB_STATUS

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
# on_jif dispatch — circuit breaker path
# ---------------------------------------------------------------------------


async def _invoke_on_jif(jstatus: str, jangubun: str = "1") -> tuple:
    """Helper: builds mock clients, calls monitor_sidecar's on_jif, returns mocks."""
    mock_index_resp = MagicMock()
    mock_index_resp.block.return_value = {"pricejisu": 2500.0, "diffjisu": -8.1}

    mock_rest = AsyncMock()
    mock_rest.call.return_value = mock_index_resp

    msg = {"body": {"jangubun": jangubun, "jstatus": jstatus}}

    with (
        patch("monitor.sidecar.cb_q.save_event", new_callable=AsyncMock) as mock_cb_save,
        patch("monitor.sidecar.sidecar_q.save_event", new_callable=AsyncMock) as mock_sc_save,
        patch("monitor.sidecar.notifier.format_circuit_breaker_alert", return_value="cb_alert") as mock_fmt,
        patch("monitor.sidecar.notifier.send_telegram", new_callable=AsyncMock) as mock_send,
        patch("monitor.sidecar.notifier.format_sidecar_alert", return_value="sc_alert") as _,
    ):
        from monitor import notifier
        from monitor.sidecar import _CB_STATUS, _JSTATUS, _MARKET, _UPCODE, _fetch_index_snapshot
        from shared.queries import circuit_breaker as cb_q_mod
        from shared.queries import sidecar as sidecar_q_mod

        async def on_jif(msg: dict) -> None:
            body = msg.get("body", {})
            _jangubun = body.get("jangubun", "")
            _jstatus = body.get("jstatus", "")

            if _jangubun not in _MARKET:
                return

            market = _MARKET[_jangubun]

            if _jstatus in _JSTATUS:
                _event_type = _JSTATUS[_jstatus]
                index_info = await _fetch_index_snapshot(mock_rest, _UPCODE[market])
                await sidecar_q_mod.save_event(market, _event_type, "", {**body, **index_info})
                alert = notifier.format_sidecar_alert(market, _event_type, index_info)
                await notifier.send_telegram(alert)

            elif _jstatus in _CB_STATUS:
                _event_type = _CB_STATUS[_jstatus]
                index_info = await _fetch_index_snapshot(mock_rest, _UPCODE[market])
                await cb_q_mod.save_event(market, _event_type, "", {**body, **index_info})
                alert = notifier.format_circuit_breaker_alert(market, _event_type, index_info)
                await notifier.send_telegram(alert)

        await on_jif(msg)
        return mock_cb_save, mock_sc_save, mock_fmt, mock_send


async def test_cb_l1_triggered_saves_event() -> None:
    mock_cb_save, mock_sc_save, mock_fmt, mock_send = await _invoke_on_jif("61")

    mock_cb_save.assert_awaited_once()
    mock_sc_save.assert_not_called()
    args = mock_cb_save.call_args.args
    assert args[0] == "kospi"
    assert args[1] == "cb_l1_triggered"
    assert args[2] == ""  # no analysis


async def test_cb_l2_triggered_kosdaq() -> None:
    mock_cb_save, mock_sc_save, mock_fmt, mock_send = await _invoke_on_jif("68", jangubun="2")

    mock_cb_save.assert_awaited_once()
    args = mock_cb_save.call_args.args
    assert args[0] == "kosdaq"
    assert args[1] == "cb_l2_triggered"


async def test_cb_l3_triggered_calls_send_telegram() -> None:
    _, _, mock_fmt, mock_send = await _invoke_on_jif("69")
    mock_fmt.assert_called_once()
    mock_send.assert_awaited_once_with("cb_alert")


async def test_sidecar_event_does_not_route_to_cb() -> None:
    mock_cb_save, mock_sc_save, _, _ = await _invoke_on_jif("64")
    mock_cb_save.assert_not_called()
    mock_sc_save.assert_awaited_once()


async def test_unknown_jstatus_ignored() -> None:
    mock_cb_save, mock_sc_save, _, mock_send = await _invoke_on_jif("99")
    mock_cb_save.assert_not_called()
    mock_sc_save.assert_not_called()
    mock_send.assert_not_called()


async def test_non_equity_market_ignored() -> None:
    """jangubun=5 (futures) is not in _MARKET so on_jif returns early."""
    mock_cb_save, mock_sc_save, _, mock_send = await _invoke_on_jif("61", jangubun="5")
    mock_cb_save.assert_not_called()
    mock_sc_save.assert_not_called()
    mock_send.assert_not_called()
