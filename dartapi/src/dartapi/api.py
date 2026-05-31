import difflib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from dartapi._internal import MetaSingleton, inherit_doc

from . import dart_event, dart_finstate, dart_list, dart_regstate, dart_report, dart_share, dart_utils
from .dart_catalog import EVENT_CATALOG, REGSTATE_CATALOG, REPORT_CATALOG

logger = logging.getLogger(__name__)


class DartAPI(metaclass=MetaSingleton):
    def __init__(self):
        self.api_key = os.getenv("DART_API_KEY", None)
        if not self.api_key:
            raise ValueError("DART_API_KEY is not set in environment variables.")
        self.__corp_codes: Optional[pd.DataFrame] = None

    def load_corp_codes(self) -> None:
        corp_codes_path = Path(__file__).parent / "db" / "corp_codes.json"
        if os.path.exists(corp_codes_path):
            with open(corp_codes_path, "r") as f:
                self.__corp_codes = pd.DataFrame(json.load(f))
            return

        logger.info(f"corp_codes.json not found at {corp_codes_path}, loading from DART API. It may take a few minutes.")
        payload = dart_list.corpCode(self.api_key)
        rows = [r for r in payload.get("list", []) if r.get("stock_code", "").strip()]
        if not rows:
            raise ValueError("Failed to load corp_codes DB.")
        self.__corp_codes = pd.DataFrame(rows)

    @property
    def corp_codes(self) -> pd.DataFrame:
        if self.__corp_codes is None:
            self.load_corp_codes()
        return self.__corp_codes

    def find_dart_corp_code(self, company_name: str) -> List[Dict[str, Any]]:
        """
        회사명을 기반으로 상장사의 DART 고유번호(corp_code) 목록을 조회합니다.

        Args:
            company_name: 조회할 회사명(정식명칭). 부분 일치 검색을 수행합니다.

        Returns:
            list[dict]: 검색 결과 레코드 목록 (상장사만 포함). 검색 결과가 없으면 빈 리스트를 반환합니다.
        """
        if not company_name:
            return []

        df = self.corp_codes

        if "corp_name" not in df.columns:
            return []

        # 상장사만 필터링 (stock_code가 공백인 경우 비상장)
        df = df[df["stock_code"].str.strip() != ""]

        # 회사명 부분 일치(대소문자 구분 없음)로 1차 필터링
        hits = df[df["corp_name"].str.contains(company_name, case=False, na=False)].copy()

        if hits.empty:
            return []

        # 유사도(SequenceMatcher.ratio)를 기준으로 정렬
        hits["similarity"] = hits["corp_name"].apply(lambda x: difflib.SequenceMatcher(None, str(x), company_name).ratio())
        hits = hits.sort_values("similarity", ascending=False)
        if not hits.empty:  # maximum 20 records
            hits = hits.iloc[:20, :].reset_index(drop=True)

        return hits.drop(columns=["similarity"]).to_dict("records")

    # -------------------------------------------------------------------------
    # 1. 공시정보
    # -------------------------------------------------------------------------

    @inherit_doc(dart_list.list)
    def search_dart_disclosures(
        self,
        api_key: str,
        corp_code: str = "",
        start: Optional[Union[str, pd.Timestamp]] = None,
        end: Optional[Union[str, pd.Timestamp]] = None,
        kind: str = "",
        kind_detail: str = "",
        final: bool = False,
        corp_cls: Optional[str] = None,
        sort: str = "date",
        sort_mth: str = "desc",
        page_no: int = 1,
        page_count: int = 100,
    ) -> Dict[str, Any]:
        return dart_list.list(
            api_key,
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

    @inherit_doc(dart_list.company)
    def get_dart_company_overview(self, api_key: str, corp_code: str) -> Dict[str, Any]:
        return dart_list.company(api_key, corp_code)

    @inherit_doc(dart_list.document)
    def fetch_dart_report_xml(self, api_key: str, rcp_no: str) -> str:
        return dart_list.document(api_key, rcp_no)

    # -------------------------------------------------------------------------
    # 3. 상장기업 재무정보
    # -------------------------------------------------------------------------

    @inherit_doc(dart_finstate.fnlttAcnt)
    def get_dart_financial_statements(
        self,
        api_key: str,
        corp_code: str,
        bsns_year: Union[str, int],
        reprt_code: str = "11011",
        fs_div: str = "CFS",
        sj_div: Optional[str] = None,
    ) -> Dict[str, Any]:
        return dart_finstate.fnlttAcnt(
            api_key,
            corp_code=corp_code,
            bsns_year=bsns_year,
            reprt_code=reprt_code,
            fs_div=fs_div,
            sj_div=sj_div,
        )

    @inherit_doc(dart_finstate.fnlttSinglAcntAll)
    def get_dart_full_financial_statements(
        self,
        api_key: str,
        corp_code: str,
        bsns_year: Union[str, int],
        reprt_code: str = "11011",
        fs_div: str = "CFS",
        sj_div: Optional[str] = None,
    ) -> Dict[str, Any]:
        return dart_finstate.fnlttSinglAcntAll(
            api_key,
            corp_code=corp_code,
            bsns_year=bsns_year,
            reprt_code=reprt_code,
            fs_div=fs_div,
            sj_div=sj_div,
        )

    @inherit_doc(dart_finstate.xbrlTaxonomy)
    def get_dart_xbrl_taxonomy(self, api_key: str, sj_div: str = "BS1") -> Dict[str, Any]:
        return dart_finstate.xbrlTaxonomy(api_key, sj_div=sj_div)

    # -------------------------------------------------------------------------
    # 4. 지분공시
    # -------------------------------------------------------------------------

    @inherit_doc(dart_share.majorstock)
    def get_dart_major_shareholding_reports(
        self,
        api_key: str,
        corp_code: str,
        start: Optional[Union[str, pd.Timestamp]] = None,
        end: Optional[Union[str, pd.Timestamp]] = None,
    ) -> Dict[str, Any]:
        return dart_share.majorstock(api_key, corp_code, start, end)

    @inherit_doc(dart_share.elestock)
    def get_dart_executive_shareholding_reports(
        self,
        api_key: str,
        corp_code: str,
        start: Optional[Union[str, pd.Timestamp]] = None,
        end: Optional[Union[str, pd.Timestamp]] = None,
    ) -> Dict[str, Any]:
        return dart_share.elestock(api_key, corp_code, start, end)

    # -------------------------------------------------------------------------
    # 5. 주요사항보고서
    # -------------------------------------------------------------------------

    def get_dart_event(
        self,
        api_key: str,
        corp_code: str,
        event_type: str,
        start: Optional[Union[str, pd.Timestamp]] = None,
        end: Optional[Union[str, pd.Timestamp]] = None,
    ) -> Dict[str, Any]:
        """주요사항보고서 이벤트를 조회합니다.

        Args:
            api_key: API 인증키. 발급받은 인증키(40자리). 필수 파라미터입니다.
            corp_code: 고유번호. 공시대상회사의 고유번호(8자리. 예: 00126380). 필수 파라미터입니다.
            event_type: 이벤트 유형. 사용 가능한 값은 dart_catalog.EVENT_CATALOG 참조.
                        예: "piicDecsn"(유상증자), "cvbdIsDecsn"(전환사채), "tsstkAqDecsn"(자기주식취득)
            start: 시작일. 검색시작 접수일자. 선택 파라미터입니다.
            end: 종료일. 검색종료 접수일자. 선택 파라미터입니다.

        Returns:
            dict: 이벤트 정보. 필드는 event_type에 따라 다름.
                  EVENT_CATALOG[event_type]["fields"]에서 필드별 상세 설명 확인 가능.
        """
        return dart_event.event(api_key, corp_code, event_type, start, end)

    def get_dart_event_catalog(self) -> Dict[str, Dict]:
        """주요사항보고서 event_type 목록 및 필드 정보를 반환합니다.

        Returns:
            dict: {event_type: {"description": str, "fields": {field: desc}}}
        """
        return EVENT_CATALOG

    # -------------------------------------------------------------------------
    # 6. 증권신고서
    # -------------------------------------------------------------------------

    def get_dart_regstate(
        self,
        api_key: str,
        corp_code: str,
        report_type: str,
        start: Optional[Union[str, pd.Timestamp]] = None,
        end: Optional[Union[str, pd.Timestamp]] = None,
    ) -> Dict[str, Any]:
        """증권신고서 정보를 조회합니다.

        Args:
            api_key: API 인증키. 발급받은 인증키(40자리). 필수 파라미터입니다.
            corp_code: 고유번호. 공시대상회사의 고유번호(8자리. 예: 00126380). 필수 파라미터입니다.
            report_type: 신고서 유형. 사용 가능한 값은 dart_catalog.REGSTATE_CATALOG 참조.
                         예: "estkRs"(지분증권), "bdRs"(채무증권), "mgRs"(합병)
            start: 시작일. 검색시작 접수일자. 선택 파라미터입니다.
            end: 종료일. 검색종료 접수일자. 선택 파라미터입니다.

        Returns:
            dict: 증권신고서 정보. 필드는 report_type에 따라 다름.
                  REGSTATE_CATALOG[report_type]["fields"]에서 필드별 상세 설명 확인 가능.
        """
        return dart_regstate.regstate(api_key, corp_code, report_type, start, end)

    def get_dart_regstate_catalog(self) -> Dict[str, Dict]:
        """증권신고서 report_type 목록 및 필드 정보를 반환합니다.

        Returns:
            dict: {report_type: {"description": str, "fields": {field: desc}}}
        """
        return REGSTATE_CATALOG

    # -------------------------------------------------------------------------
    # 2. 사업보고서 (정기보고서)
    # -------------------------------------------------------------------------

    def get_dart_report(
        self,
        api_key: str,
        corp_code: str,
        report_type: str,
        bsns_year: Union[str, int],
        reprt_code: str = "11011",
    ) -> Dict[str, Any]:
        """정기보고서(사업/분기/반기보고서) 내 세부 항목을 조회합니다.

        Args:
            api_key: API 인증키. 발급받은 인증키(40자리). 필수 파라미터입니다.
            corp_code: 고유번호. 공시대상회사의 고유번호(8자리. 예: 00126380). 필수 파라미터입니다.
            report_type: 조회 항목. 사용 가능한 값은 dart_catalog.REPORT_CATALOG 참조.
                         예: "exctvSttus"(임원현황), "empSttus"(직원현황), "alotMatter"(배당)
            bsns_year: 사업연도(4자리). 2015년 이후부터 정보제공됩니다.
            reprt_code: 보고서 코드. "11011"(사업), "11012"(반기), "11013"(1분기), "11014"(3분기).

        Returns:
            dict: 정기보고서 정보. 필드는 report_type에 따라 다름.
                  REPORT_CATALOG[report_type]["fields"]에서 필드별 상세 설명 확인 가능.
        """
        return dart_report.report(api_key, corp_code, report_type, bsns_year, reprt_code)

    def get_dart_report_catalog(self) -> Dict[str, Dict]:
        """정기보고서 report_type 목록 및 필드 정보를 반환합니다.

        Returns:
            dict: {report_type: {"description": str, "fields": {field: desc}}}
        """
        return REPORT_CATALOG

    # -------------------------------------------------------------------------
    # 7. DART HTML 유틸리티 (dart_utils)
    # -------------------------------------------------------------------------

    @inherit_doc(dart_utils.list_dart_disclosures_by_date)
    def list_dart_disclosures_by_date(self, date: str, start_page: int = 1, end_page: int = 10) -> List[Dict[str, Any]]:
        return dart_utils.list_dart_disclosures_by_date(date, start_page, end_page)

    @inherit_doc(dart_utils.get_dart_report_sub_documents)
    def get_dart_report_sub_documents(self, rcp_no: str, match: Optional[str] = None) -> List[Dict[str, Any]]:
        return dart_utils.get_dart_report_sub_documents(rcp_no, match)

    @inherit_doc(dart_utils.get_dart_report_attached_documents)
    def get_dart_report_attached_documents(self, rcp_no: str, match: Optional[str] = None) -> List[Dict[str, Any]]:
        return dart_utils.get_dart_report_attached_documents(rcp_no, match)

    @inherit_doc(dart_utils.get_dart_report_downloadable_attachments)
    def get_dart_document_downloadable_attachments(self, arg: str) -> Dict[str, str]:
        return dart_utils.get_dart_report_downloadable_attachments(arg)

    @inherit_doc(dart_utils.extract_dart_viewer_content)
    def extract_dart_viewer_content(self, url: str) -> str:
        return dart_utils.extract_dart_viewer_content(url)
