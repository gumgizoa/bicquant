import inspect

import pytest

from dartapi.dart_catalog import (
    EVENT_RETURN_FIELDS_CATALOG,
    get_dart_return_fields,
    list_dart_return_fields_catalog,
)
from dartapi.dart_list import document
from dartapi.dart_utils import get_dart_report_attached_documents, get_dart_report_sub_documents
from dartapi.server import DartServerState, _validate_api_key, create_server


def test_return_fields_catalog_name_is_explicit() -> None:
    assert "piicDecsn" in EVENT_RETURN_FIELDS_CATALOG


def test_catalog_lookup_returns_summary_and_selected_fields() -> None:
    event_catalog = list_dart_return_fields_catalog("event")
    event_fields = get_dart_return_fields("event", "piicDecsn")

    assert event_catalog["piicDecsn"] == "유상증자 결정"
    assert event_fields["fields"]["corp_cls"].startswith("법인구분")
    assert event_fields["fields"]["nstk_ostk_cnt"].startswith("신주의 종류와 수")


def test_catalog_helpers_raise_useful_errors() -> None:
    with pytest.raises(ValueError, match="Unknown catalog_name"):
        list_dart_return_fields_catalog("missing")

    with pytest.raises(ValueError, match="Unknown item_type"):
        get_dart_return_fields("event", "missing")


def test_report_document_helpers_use_rcept_no_parameter() -> None:
    assert "rcept_no" in inspect.signature(document).parameters
    assert "rcp_no" not in inspect.signature(document).parameters
    assert "rcept_no" in inspect.signature(get_dart_report_sub_documents).parameters
    assert "rcept_no" in inspect.signature(get_dart_report_attached_documents).parameters


def test_create_server_without_dart_api_key() -> None:
    server = create_server()

    assert server.name == "DART OpenAPI"


def test_validate_api_key_rejects_missing_or_malformed_key() -> None:
    with pytest.raises(ValueError, match="DART_API_KEY is not set"):
        _validate_api_key(None)

    with pytest.raises(ValueError, match="40 characters"):
        _validate_api_key("short")


def test_server_state_get_client_uses_env_api_key_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DART_API_KEY", "x" * 40)
    state = DartServerState()

    client = state.get_client()

    assert client.params["crtfc_key"] == "x" * 40
    state.close()
    assert state.client is None
