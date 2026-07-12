"""Listed-company corp_code lookups, backed by a cached DART corpCode snapshot.

Kept free of MCP/server imports so non-MCP callers (e.g. the monitor service)
can map tickers to corp_codes without pulling in FastMCP.

The snapshot at ``db/corp_codes.json`` is a point-in-time export: companies
listed after it was taken are absent. Renames do not matter because corp_code
is stable, but ``stock_code`` for a fresh IPO will simply miss. Refresh the
snapshot with :func:`refresh_corp_codes` when that starts to bite.
"""

import difflib
import json
import logging
from pathlib import Path
from typing import Any, Optional

import httpx
import pandas as pd

from . import dart_list

logger = logging.getLogger(__name__)

CORP_CODES_PATH = Path(__file__).parent / "db" / "corp_codes.json"

_corp_codes: Optional[pd.DataFrame] = None


def _fetch_from_dart(client: httpx.Client) -> pd.DataFrame:
    """Download the full corpCode list from DART, keeping listed companies only."""
    logger.info("Loading corp_codes from the DART API. It may take a few minutes.")
    payload = dart_list.corpCode(client)
    rows = [row for row in payload.get("list", []) if row.get("stock_code", "").strip()]
    if not rows:
        raise ValueError("Failed to load corp_codes DB.")
    return pd.DataFrame(rows)


def load_corp_codes(client: Optional[httpx.Client] = None) -> pd.DataFrame:
    """Return the cached listed-company corp_code table.

    Reads ``db/corp_codes.json`` when present. Otherwise ``client`` is required
    to download the table from DART.
    """
    global _corp_codes
    if _corp_codes is not None:
        return _corp_codes

    if CORP_CODES_PATH.exists():
        with CORP_CODES_PATH.open("r", encoding="utf-8") as f:
            _corp_codes = pd.DataFrame(json.load(f))
        return _corp_codes

    if client is None:
        raise ValueError(f"corp_codes.json not found at {CORP_CODES_PATH} and no DART client was given to rebuild it.")

    _corp_codes = _fetch_from_dart(client)
    return _corp_codes


def refresh_corp_codes(client: httpx.Client) -> pd.DataFrame:
    """Re-download the corp_code table from DART and overwrite the cached snapshot."""
    global _corp_codes
    df = _fetch_from_dart(client)
    CORP_CODES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CORP_CODES_PATH.open("w", encoding="utf-8") as f:
        json.dump(df.to_dict("records"), f, ensure_ascii=False)
    _corp_codes = df
    return df


def map_stock_codes_to_corp_codes(stock_codes: list[str], client: Optional[httpx.Client] = None) -> dict[str, str]:
    """Map 6-digit tickers to 8-digit DART corp_codes.

    Tickers missing from the snapshot are omitted, so the caller can tell which
    ones went unmapped by diffing against its input.
    """
    df = load_corp_codes(client)
    lookup = dict(zip(df["stock_code"].str.strip(), df["corp_code"].str.strip()))
    return {code: lookup[code] for code in (c.strip() for c in stock_codes) if code in lookup}


def find_corp_codes_by_name(company_name: str, client: Optional[httpx.Client] = None) -> list[dict[str, Any]]:
    """Find listed company corp_code candidates by company name, best match first."""
    if not company_name:
        raise ValueError(f"company_name should not be empty. Given: {company_name}")

    df = load_corp_codes(client)

    listed = df[df["stock_code"].str.strip() != ""]
    hits = listed[listed["corp_name"].str.contains(company_name, case=False, na=False)].copy()
    if hits.empty:
        suggestion = (
            f"입력한 회사명 '{company_name}'으로 조회된 결과가 없습니다. "
            "상장회사의 경우, 다음과 같이 시도를 권장합니다:\n"
            "- 회사명을 영문 이니셜/대문자로 입력해보세요 (예: '네이버' → 'NAVER', '포스코' → 'POSCO')\n"
            "- 회사명에 '주식회사', 공백, 특수문자를 제거해보세요\n"
            "- 공식 상장명(증권사 검색 명칭)과 일치하는지 확인해보세요\n"
            "그래도 조회가 안될 경우 DART 전자공시 상장명칭을 참고해주세요."
        )
        return [{"message": suggestion}]

    hits["similarity"] = hits["corp_name"].apply(lambda name: difflib.SequenceMatcher(None, str(name), company_name).ratio())
    hits = hits.sort_values("similarity", ascending=False).iloc[:20, :].reset_index(drop=True)
    return hits.drop(columns=["similarity"]).to_dict("records")
