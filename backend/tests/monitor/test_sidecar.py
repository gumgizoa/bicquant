"""Unit tests for monitor.sidecar and monitor.notifier sidecar formatting."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from monitor.notifier import format_sidecar_alert
from monitor.sidecar import _JSTATUS, _MARKET, _fetch_index_snapshot

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
# _fetch_index_snapshot
# ---------------------------------------------------------------------------


async def test_fetch_index_snapshot_returns_formatted_values() -> None:
    mock_resp = MagicMock()
    mock_resp.block.return_value = {"pricejisu": 2700.50, "diffjisu": -3.55}

    mock_client = AsyncMock()
    mock_client.call.return_value = mock_resp

    result = await _fetch_index_snapshot(mock_client, "001")

    mock_client.call.assert_awaited_once_with("t1511", {"t1511InBlock": {"upcode": "001"}})
    assert result["current"] == "2,700.50"
    assert result["change_pct"] == "-3.55"


async def test_fetch_index_snapshot_returns_empty_on_error() -> None:
    mock_client = AsyncMock()
    mock_client.call.side_effect = Exception("network error")

    result = await _fetch_index_snapshot(mock_client, "001")

    assert result == {}


async def test_fetch_index_snapshot_handles_missing_block() -> None:
    mock_resp = MagicMock()
    mock_resp.block.return_value = None

    mock_client = AsyncMock()
    mock_client.call.return_value = mock_resp

    result = await _fetch_index_snapshot(mock_client, "001")

    assert result["current"] == "0.00"
    assert result["change_pct"] == "+0.00"
