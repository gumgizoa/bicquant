"""Tests for dartapi.corp_codes — the ticker -> corp_code mapping.

Runs offline against the bundled corp_codes.json snapshot.
"""

import pytest

from dartapi.corp_codes import find_corp_codes_by_name, load_corp_codes, map_stock_codes_to_corp_codes

_SAMSUNG_TICKER = "005930"
_SAMSUNG_CORP_CODE = "00126380"


def test_load_corp_codes_has_expected_columns() -> None:
    df = load_corp_codes()
    assert {"corp_code", "corp_name", "stock_code"}.issubset(df.columns)
    assert not df.empty


def test_stock_code_is_a_unique_key() -> None:
    # The whole watchlist filter rests on this: one ticker maps to exactly one corp_code.
    df = load_corp_codes()
    stock_codes = df["stock_code"].str.strip()
    assert stock_codes.is_unique
    assert df["corp_code"].str.strip().is_unique


def test_map_stock_codes_to_corp_codes() -> None:
    assert map_stock_codes_to_corp_codes([_SAMSUNG_TICKER]) == {_SAMSUNG_TICKER: _SAMSUNG_CORP_CODE}


def test_map_stock_codes_drops_unknown_tickers() -> None:
    # An unmapped ticker is omitted rather than guessed at, so callers can spot it.
    result = map_stock_codes_to_corp_codes([_SAMSUNG_TICKER, "999999"])
    assert result == {_SAMSUNG_TICKER: _SAMSUNG_CORP_CODE}


def test_map_stock_codes_empty_input() -> None:
    assert map_stock_codes_to_corp_codes([]) == {}


def test_find_corp_codes_by_name_returns_best_match_first() -> None:
    hits = find_corp_codes_by_name("삼성전자")
    assert hits[0]["corp_code"] == _SAMSUNG_CORP_CODE


def test_find_corp_codes_by_name_unknown_returns_suggestion() -> None:
    hits = find_corp_codes_by_name("존재하지않는회사명")
    assert "message" in hits[0]


def test_find_corp_codes_by_name_rejects_empty() -> None:
    with pytest.raises(ValueError):
        find_corp_codes_by_name("")
