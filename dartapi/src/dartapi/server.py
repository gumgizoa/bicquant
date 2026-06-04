# -*- coding:utf-8 -*-
"""MCP server for DART OpenAPI tools."""

import difflib
import inspect
import json
import logging
import os
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, Optional, Union

import httpx
import pandas as pd
from mcp.server.fastmcp import FastMCP

from dartapi.exceptions import APIError

from . import dart_catalog, dart_event, dart_finstate, dart_list, dart_regstate, dart_report, dart_share, dart_utils

logger = logging.getLogger(__name__)

SERVER_INSTRUCTIONS = """
You are using dartapi, a DART OpenAPI MCP server for Korean corporate disclosures.

## Recommended Workflow
- Use `find_dart_corp_code` first when the user gives a company name.
- Use `search_dart_disclosures` to find disclosure reports and `rcept_no`.
- Use `get_dart_company_overview` for company profile information.
- Tool descriptions document each tool's parameters (pulled from the wrapped functions) but omit
  return fields. For return field meanings, call the catalog tools below.

## Progressive Field Disclosure
- `list_dart_return_fields_catalog`: list item types in a catalog (event, report, regstate, share, finstate, list).
- `get_dart_return_fields`: inspect return fields for one item type.
"""


def _validate_api_key(api_key: str | None) -> str:
    """Validate the DART API key.

    Args:
        api_key: DART API key from the environment.

    Returns:
        Validated DART API key.

    Raises:
        ValueError: If the key is missing or malformed.
    """
    if not api_key:
        raise ValueError("DART_API_KEY is not set in environment variables.")
    if len(api_key) != 40:
        raise ValueError("DART_API_KEY must be 40 characters.")
    return api_key


class DartServerState:
    """State owned by one DART MCP server instance."""

    def __init__(self) -> None:
        self.client: httpx.Client | None = None
        self.corp_codes: pd.DataFrame | None = None

    def get_client(self) -> httpx.Client:
        """Return this server instance's DART OpenAPI client."""
        if self.client is None:
            api_key = _validate_api_key(os.getenv("DART_API_KEY"))
            self.client = httpx.Client(params={"crtfc_key": api_key})
        return self.client

    def close(self) -> None:
        """Close this server instance's DART OpenAPI client."""
        if self.client is not None:
            self.client.close()
            self.client = None

    def load_corp_codes(self) -> pd.DataFrame:
        """Load and cache listed DART company codes for this server instance."""
        if self.corp_codes is not None:
            return self.corp_codes

        corp_codes_path = Path(__file__).parent / "db" / "corp_codes.json"
        if corp_codes_path.exists():
            with corp_codes_path.open("r", encoding="utf-8") as f:
                self.corp_codes = pd.DataFrame(json.load(f))
            return self.corp_codes

        logger.info("corp_codes.json not found at %s, loading from DART API. It may take a few minutes.", corp_codes_path)
        payload = dart_list.corpCode(self.get_client())
        rows = [row for row in payload.get("list", []) if row.get("stock_code", "").strip()]
        if not rows:
            raise ValueError("Failed to load corp_codes DB.")
        self.corp_codes = pd.DataFrame(rows)
        return self.corp_codes

    def find_dart_corp_code(self, company_name: str) -> list[dict[str, Any]]:
        """Find listed company DART corp_code candidates by company name."""
        if not company_name:
            raise ValueError(f"company_name should not be empty. Given: {company_name}")

        df = self.load_corp_codes()

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


def _json_resource(payload: Any) -> str:
    """Serialize MCP resource payloads as formatted JSON."""
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _handle_tool_error(func: Callable[..., Any]) -> Callable[..., Any]:
    """Return structured errors instead of raising through MCP tools."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except APIError as exc:
            return {"error": {"code": exc.code, "message": exc.message}}
        except ValueError as exc:
            return {"error": {"code": "INVALID_ARGUMENT", "message": str(exc)}}
        except Exception as exc:  # pragma: no cover - defensive MCP boundary
            logger.exception("Unexpected DART MCP tool error")
            return {"error": {"code": "INTERNAL_ERROR", "message": str(exc)}}

    return wrapper


def _tool_doc(src_fn: Callable[..., Any]) -> str:
    """Build an MCP tool description from a wrapped function's docstring.

    The `client:` Args line is dropped because MCP tools inject the DART client
    internally and do not expose it as a parameter.
    """
    doc = inspect.getdoc(src_fn) or ""
    return "\n".join(line for line in doc.splitlines() if not line.lstrip().startswith("client:"))


def create_server(state: DartServerState | None = None) -> FastMCP:
    """Create and configure the DART MCP server."""
    state = state or DartServerState()
    server = FastMCP("DART OpenAPI", instructions=SERVER_INSTRUCTIONS)

    @server.resource(
        "dart://return-fields/{catalog_name}",
        name="dart-return-fields-catalog",
        description="Summary of item types available in a DART return fields catalog: event, report, or regstate.",
        mime_type="application/json",
    )
    def return_fields_catalog_resource(catalog_name: str) -> str:
        """Return item type descriptions for one return fields catalog as JSON."""
        return _json_resource(dart_catalog.list_dart_return_fields_catalog(catalog_name))

    @server.tool(description=_tool_doc(dart_catalog.list_dart_return_fields_catalog))
    @_handle_tool_error
    def list_dart_return_fields_catalog(catalog_name: str) -> dict[str, str]:
        return dart_catalog.list_dart_return_fields_catalog(catalog_name)

    @server.tool(description=_tool_doc(dart_catalog.get_dart_return_fields))
    @_handle_tool_error
    def get_dart_return_fields(catalog_name: str, item_type: str) -> dict[str, Any]:
        return dart_catalog.get_dart_return_fields(catalog_name, item_type)

    @server.tool()
    @_handle_tool_error
    def find_dart_corp_code(company_name: str) -> list[dict[str, Any]]:
        """Find listed company DART corp_code candidates by Korean company name."""
        return state.find_dart_corp_code(company_name)

    # ---- 공시정보 ---- #
    @server.tool(description=_tool_doc(dart_list.list))
    @_handle_tool_error
    def search_dart_disclosures(
        corp_code: str = "",
        start: Optional[str] = None,
        end: Optional[str] = None,
        kind: str = "",
        kind_detail: str = "",
        final: bool = False,
        corp_cls: Optional[str] = None,
        sort: str = "date",
        sort_mth: str = "desc",
        page_no: int = 1,
        page_count: int = 100,
    ) -> dict[str, Any]:
        return dart_list.list(
            state.get_client(),
            corp_code=corp_code,
            start=start,
            end=end,
            kind=kind,
            kind_detail=kind_detail,
            final=final,
            corp_cls=corp_cls,
            sort=sort,
            sort_mth=sort_mth,
            page_no=page_no,
            page_count=page_count,
        )

    @server.tool(description=_tool_doc(dart_list.company))
    @_handle_tool_error
    def get_dart_company_overview(corp_code: str) -> dict[str, Any]:
        return dart_list.company(state.get_client(), corp_code)

    @server.tool(description=_tool_doc(dart_list.document))
    @_handle_tool_error
    def fetch_dart_report_xml(rcept_no: str) -> str:
        return dart_list.document(state.get_client(), rcept_no)

    # ---- 정기보고서 주요정보 ---- #
    @server.tool(description=_tool_doc(dart_report.report))
    @_handle_tool_error
    def get_dart_report(
        corp_code: str,
        report_type: str,
        bsns_year: Union[str, int],
        reprt_code: str = "11011",
    ) -> dict[str, Any]:
        return dart_report.report(state.get_client(), corp_code, report_type, bsns_year, reprt_code)

    @server.tool()
    @_handle_tool_error
    def get_dart_report_catalog() -> dict[str, dict[str, Any]]:
        """Get report types and return fields for periodic reports."""
        return dart_catalog.REPORT_RETURN_FIELDS_CATALOG

    # ---- 정기보고서 재무정보 ---- #
    @server.tool(description=_tool_doc(dart_finstate.fnlttAcnt))
    @_handle_tool_error
    def get_dart_financial_statements(
        corp_code: str,
        bsns_year: Union[str, int],
        reprt_code: str = "11011",
        fs_div: str = "CFS",
        sj_div: Optional[str] = None,
    ) -> dict[str, Any]:
        return dart_finstate.fnlttAcnt(
            state.get_client(),
            corp_code=corp_code,
            bsns_year=bsns_year,
            reprt_code=reprt_code,
            fs_div=fs_div,
            sj_div=sj_div,
        )

    @server.tool(description=_tool_doc(dart_finstate.fnlttSinglAcntAll))
    @_handle_tool_error
    def get_dart_full_financial_statements(
        corp_code: str,
        bsns_year: Union[str, int],
        reprt_code: str = "11011",
        fs_div: str = "CFS",
        sj_div: Optional[str] = None,
    ) -> dict[str, Any]:
        return dart_finstate.fnlttSinglAcntAll(
            state.get_client(),
            corp_code=corp_code,
            bsns_year=bsns_year,
            reprt_code=reprt_code,
            fs_div=fs_div,
            sj_div=sj_div,
        )

    @server.tool(description=_tool_doc(dart_finstate.xbrlTaxonomy))
    @_handle_tool_error
    def get_dart_xbrl_taxonomy(sj_div: str = "BS1") -> dict[str, Any]:
        return dart_finstate.xbrlTaxonomy(state.get_client(), sj_div=sj_div)

    # ---- 지분공시 종합정보 ---- #
    @server.tool(description=_tool_doc(dart_share.majorstock))
    @_handle_tool_error
    def get_dart_major_shareholding_reports(
        corp_code: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> dict[str, Any]:
        return dart_share.majorstock(state.get_client(), corp_code, start, end)

    @server.tool(description=_tool_doc(dart_share.elestock))
    @_handle_tool_error
    def get_dart_executive_shareholding_reports(
        corp_code: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> dict[str, Any]:
        return dart_share.elestock(state.get_client(), corp_code, start, end)

    # ---- 주요사항보고서 주요정보 ---- #
    @server.tool(description=_tool_doc(dart_event.event))
    @_handle_tool_error
    def get_dart_event(
        corp_code: str,
        event_type: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> dict[str, Any]:
        return dart_event.event(state.get_client(), corp_code, event_type, start, end)

    @server.tool()
    @_handle_tool_error
    def get_dart_event_catalog() -> dict[str, dict[str, Any]]:
        """Get event types and return fields for major event reports."""
        return dart_catalog.EVENT_RETURN_FIELDS_CATALOG

    # ---- 증권신고서 주요정보 ---- #
    @server.tool(description=_tool_doc(dart_regstate.regstate))
    @_handle_tool_error
    def get_dart_regstate(
        corp_code: str,
        report_type: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> dict[str, Any]:
        return dart_regstate.regstate(state.get_client(), corp_code, report_type, start, end)

    @server.tool()
    @_handle_tool_error
    def get_dart_regstate_catalog() -> dict[str, dict[str, Any]]:
        """Get report types and return fields for registration statements."""
        return dart_catalog.REGSTATE_RETURN_FIELDS_CATALOG

    # ---- DART unofficial utilities ---- #
    @server.tool(description=_tool_doc(dart_utils.list_dart_disclosures_by_date))
    @_handle_tool_error
    def list_dart_disclosures_by_date(date: str, start_page: int = 1, end_page: int = 10) -> list[dict[str, Any]]:
        return dart_utils.list_dart_disclosures_by_date(date, start_page, end_page)

    @server.tool(description=_tool_doc(dart_utils.get_dart_report_sub_documents))
    @_handle_tool_error
    def get_dart_report_sub_documents(rcept_no: str, match: Optional[str] = None) -> list[dict[str, Any]]:
        return dart_utils.get_dart_report_sub_documents(rcept_no, match)

    @server.tool(description=_tool_doc(dart_utils.get_dart_report_attached_documents))
    @_handle_tool_error
    def get_dart_report_attached_documents(rcept_no: str, match: Optional[str] = None) -> list[dict[str, Any]]:
        return dart_utils.get_dart_report_attached_documents(rcept_no, match)

    @server.tool(description=_tool_doc(dart_utils.get_dart_report_downloadable_attachments))
    @_handle_tool_error
    def get_dart_document_downloadable_attachments(arg: str) -> dict[str, str]:
        return dart_utils.get_dart_report_downloadable_attachments(arg)

    @server.tool(description=_tool_doc(dart_utils.extract_dart_viewer_content))
    @_handle_tool_error
    def extract_dart_viewer_content(url: str) -> str:
        return dart_utils.extract_dart_viewer_content(url)

    logger.info("DART MCP server initialized with 22 tools and 1 resource")
    return server


def main() -> None:
    """Run the DART MCP server over the default FastMCP transport."""
    create_server().run()


if __name__ == "__main__":
    main()
