"""Unit tests for LSWebSocketClient.connect() retry behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import websockets.exceptions

from lsapi.ws_client import LSWebSocketClient


def _conn_closed_ok() -> websockets.exceptions.ConnectionClosedOK:
    """Create a ConnectionClosedOK without requiring valid Close frame objects."""
    return websockets.exceptions.ConnectionClosedOK.__new__(websockets.exceptions.ConnectionClosedOK)


# ---------------------------------------------------------------------------
# connect() retry on ConnectionClosedOK
# ---------------------------------------------------------------------------


async def test_connect_retries_once_on_connection_closed_ok() -> None:
    """connect() must retry when the server closes the connection during login."""
    client = LSWebSocketClient("key", "secret", reconnect_delay=0)
    login_calls = 0

    async def fake_login(token: str) -> None:
        nonlocal login_calls
        login_calls += 1
        if login_calls == 1:
            raise _conn_closed_ok()

    mock_conn = AsyncMock()

    with (
        patch.object(client._tokens, "get", new_callable=AsyncMock, return_value="tok"),
        patch("lsapi.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_conn),
        patch.object(client, "_login", side_effect=fake_login),
        patch("lsapi.ws_client.asyncio.create_task"),
    ):
        await client.connect()

    assert login_calls == 2


async def test_connect_retries_multiple_times_before_succeeding() -> None:
    client = LSWebSocketClient("key", "secret", reconnect_delay=0)
    login_calls = 0

    async def fake_login(token: str) -> None:
        nonlocal login_calls
        login_calls += 1
        if login_calls < 3:
            raise _conn_closed_ok()

    mock_conn = AsyncMock()

    with (
        patch.object(client._tokens, "get", new_callable=AsyncMock, return_value="tok"),
        patch("lsapi.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_conn),
        patch.object(client, "_login", side_effect=fake_login),
        patch("lsapi.ws_client.asyncio.create_task"),
    ):
        await client.connect()

    assert login_calls == 3


async def test_connect_does_not_retry_when_stopping() -> None:
    """connect() exits without creating a task when _stopping is True during retry."""
    client = LSWebSocketClient("key", "secret", reconnect_delay=0)
    client._stopping = True

    async def fake_login(token: str) -> None:
        raise _conn_closed_ok()

    mock_conn = AsyncMock()
    mock_create_task = MagicMock()

    with (
        patch.object(client._tokens, "get", new_callable=AsyncMock, return_value="tok"),
        patch("lsapi.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_conn),
        patch.object(client, "_login", side_effect=fake_login),
        patch("lsapi.ws_client.asyncio.create_task", mock_create_task),
    ):
        await client.connect()

    mock_create_task.assert_not_called()


async def test_connect_succeeds_on_first_try_without_retry() -> None:
    client = LSWebSocketClient("key", "secret", reconnect_delay=0)
    login_calls = 0

    async def fake_login(token: str) -> None:
        nonlocal login_calls
        login_calls += 1

    mock_conn = AsyncMock()

    with (
        patch.object(client._tokens, "get", new_callable=AsyncMock, return_value="tok"),
        patch("lsapi.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_conn),
        patch.object(client, "_login", side_effect=fake_login),
        patch("lsapi.ws_client.asyncio.create_task"),
    ):
        await client.connect()

    assert login_calls == 1


async def test_connect_creates_recv_task_after_successful_login() -> None:
    client = LSWebSocketClient("key", "secret", reconnect_delay=0)
    mock_conn = AsyncMock()
    mock_create_task = MagicMock()

    with (
        patch.object(client._tokens, "get", new_callable=AsyncMock, return_value="tok"),
        patch("lsapi.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_conn),
        patch.object(client, "_login", new_callable=AsyncMock),
        patch("lsapi.ws_client.asyncio.create_task", mock_create_task),
    ):
        await client.connect()

    mock_create_task.assert_called_once()


async def test_connect_propagates_non_closed_ok_exceptions() -> None:
    """connect() should not swallow unexpected exceptions from login."""
    client = LSWebSocketClient("key", "secret", reconnect_delay=0)
    mock_conn = AsyncMock()

    with (
        patch.object(client._tokens, "get", new_callable=AsyncMock, return_value="tok"),
        patch("lsapi.ws_client.websockets.connect", new_callable=AsyncMock, return_value=mock_conn),
        patch.object(client, "_login", side_effect=RuntimeError("unexpected")),
        patch("lsapi.ws_client.asyncio.create_task"),
    ):
        import pytest

        with pytest.raises(RuntimeError, match="unexpected"):
            await client.connect()
