"""Tests for monitor notifier formatting helpers."""

from monitor.notifier import format_service_error_alert


def test_format_service_error_alert_contains_context_and_exception() -> None:
    exc = RuntimeError("boom")

    msg = format_service_error_alert("Deviation poll", exc)

    assert "서비스 에러" in msg
    assert "Deviation poll" in msg
    assert "RuntimeError" in msg
    assert "boom" in msg


def test_format_service_error_alert_escapes_html() -> None:
    exc = ValueError("bad <token> & secret")

    msg = format_service_error_alert("DART <poll>", exc)

    assert "DART &lt;poll&gt;" in msg
    assert "bad &lt;token&gt; &amp; secret" in msg
