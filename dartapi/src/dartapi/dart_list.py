# -*- coding:utf-8 -*-
# 2020-2023 FinanceData.KR http://financedata.kr fb.com/financedata

import io
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from typing import Any, Dict, Optional, Union

import pandas as pd
import requests

from dartapi.exceptions import APIError

from .dart_parser import parse_dart_to_text


def list(
    api_key: str,
    corp_code: str = "",
    start: Optional[Union[str, datetime]] = None,
    end: Optional[Union[str, datetime]] = None,
    kind: str = "",
    kind_detail: str = "",
    final: bool = False,
    corp_cls: Optional[str] = None,
    sort: str = "date",
    sort_mth: str = "desc",
    page_no: int = 1,
    page_count: int = 100,
) -> Dict[str, Any]:
    """공시정보를 검색합니다.

    공시 유형별, 회사별, 날짜별 등 여러가지 조건으로 공시보고서 검색기능을 제공합니다.
    모든 페이지를 자동으로 가져와서 반환합니다.

    Args:
        api_key: API 인증키. 발급받은 인증키(40자리). 필수 파라미터입니다.
        corp_code: 고유번호. 공시대상회사의 고유번호(8자리. 예: 00120182). 선택 파라미터입니다.
                  고유번호가 없는 경우 검색기간은 3개월로 제한됩니다.
        start: 시작일. 검색시작 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.
        end: 종료일. 검색종료 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.
        kind: 공시유형. 선택 파라미터입니다. 다음 중 하나를 선택할 수 있습니다:
              - "A": 정기공시
              - "B": 주요사항보고
              - "C": 발행공시
              - "D": 지분공시
              - "E": 기타공시
              - "F": 외부감사관련
              - "G": 펀드공시
              - "H": 자산유동화
              - "I": 거래소공시
              - "J": 공정위공시
        kind_detail: 공시상세유형. 선택 파라미터입니다.
              - "A001": "사업보고서"
              - "A002": "반기보고서"
              - "A003": "분기보고서"
              - "A004": "등록법인결산서류(자본시장법이전)"
              - "A005": "소액공모법인결산서류"
              - "B001": "주요사항보고서"
              - "B002": "주요경영사항신고(자본시장법 이전)"
              - "B003": "최대주주등과의거래신고(자본시장법 이전)"
              - "C001": "증권신고(지분증권)"
              - "C002": "증권신고(채무증권)"
              - "C003": "증권신고(파생결합증권)"
              - "C004": "증권신고(합병등)"
              - "C005": "증권신고(기타)"
              - "C006": "소액공모(지분증권)"
              - "C007": "소액공모(채무증권)"
              - "C008": "소액공모(파생결합증권)"
              - "C009": "소액공모(합병등)"
              - "C010": "소액공모(기타)"
              - "C011": "호가중개시스템을통한소액매출"
              - "D001": "주식등의대량보유상황보고서"
              - "D002": "임원ㆍ주요주주특정증권등소유상황보고서"
              - "D003": "의결권대리행사권유"
              - "D004": "공개매수"
              - "D005": "임원ㆍ주요주주 특정증권등 거래계획보고서"
              - "E001": "자기주식취득/처분"
              - "E002": "신탁계약체결/해지"
              - "E003": "합병등종료보고서"
              - "E004": "주식매수선택권부여에관한신고"
              - "E005": "사외이사에관한신고"
              - "E006": "주주총회소집보고서"
              - "E007": "시장조성/안정조작"
              - "E008": "합병등신고서(자본시장법 이전)"
              - "E009": "금융위등록/취소(자본시장법 이전)"
              - "E010": "이중상환청구권부채권(커버드본드)"
              - "F001": "감사보고서"
              - "F002": "연결감사보고서"
              - "F003": "결합감사보고서"
              - "F004": "회계법인사업보고서"
              - "F005": "감사전재무제표미제출신고서"
              - "G001": "증권신고(집합투자증권-신탁형)"
              - "G002": "증권신고(집합투자증권-회사형)"
              - "G003": "증권신고(집합투자증권-합병)"
              - "H001": "자산유동화계획/양도등록"
              - "H002": "사업/반기/분기보고서"
              - "H003": "증권신고(유동화증권등)"
              - "H004": "채권유동화계획/양도등록"
              - "H005": "자산유동화관련중요사항발생등보고"
              - "H006": "주요사항보고서"
              - "I001": "수시공시"
              - "I002": "공정공시"
              - "I003": "시장조치/안내"
              - "I004": "지분공시"
              - "I005": "증권투자회사"
              - "I006": "채권공시"
              - "J001": "대규모내부거래관련"
              - "J002": "대규모내부거래관련(구)"
              - "J004": "기업집단현황공시"
              - "J005": "비상장회사중요사항공시"
              - "J006": "기타공정위공시"
              - "J008": "대규모내부거래관련(공익법인용)"
              - "J009": "하도급대금결제조건공시"
        final: 최종보고서 검색여부. 선택 파라미터입니다.
               True인 경우 최종보고서만 검색 (정정이 있는 경우 최종정정만 검색).
               기본값: False
        corp_cls: 법인구분. 선택 파라미터입니다. 다음 중 하나를 선택할 수 있습니다:
                  - "Y": 유가
                  - "K": 코스닥
                  - "N": 코넥스
                  - "E": 기타
                  없으면 전체조회, 복수조건 불가
        sort: 정렬. 선택 파라미터입니다. 다음 중 하나를 선택할 수 있습니다:
              - "date": 접수일자
              - "crp": 회사명
              - "rpt": 보고서명
              기본값: "date"
        sort_mth: 정렬방법. 선택 파라미터입니다. 다음 중 하나를 선택할 수 있습니다:
                  - "asc": 오름차순
                  - "desc": 내림차순
                  기본값: "desc"
        page_no: 페이지 번호. 선택 파라미터입니다. 기본값: 1
        page_count: 페이지 별 건수. 선택 파라미터입니다. 기본값: 100, 최대값: 100

    Returns:
        dict: 공시정보를 담은 딕셔너리. 다음 구조를 가집니다:
            - status (str): 에러 및 정보 코드
            - message (str): 에러 및 정보 메시지
            - page_no (str): 페이지 번호
            - page_count (str): 페이지 별 건수
            - total_count (str): 총 건수
            - total_page (str): 총 페이지 수
            - list (list): 공시정보 배열. 각 항목은 다음 필드를 포함:
                - corp_cls (str): 법인구분 (Y:유가, K:코스닥, N:코넥스, E:기타)
                - corp_name (str): 종목명(법인명) (공시대상회사의 종목명(상장사) 또는 법인명(기타법인))
                - corp_code (str): 고유번호 (공시대상회사의 고유번호 8자리)
                - stock_code (str): 종목코드 (상장회사의 종목코드 6자리)
                - report_nm (str): 보고서명 (공시구분+보고서명+기타정보)
                - rcept_no (str): 접수번호(14자리). 접수번호(rcept_no)를 이용하여 공시뷰어에 접근할 수 있습니다.
                - flr_nm (str): 공시 제출인명
                - rcept_dt (str): 접수일자 (공시 접수일자 YYYYMMDD)
                - rm (str): 비고. 조합된 문자로 각각은 아래와 같은 의미가 있음:
                    - 유: 본 공시사항은 한국거래소 유가증권시장본부 소관임
                    - 코: 본 공시사항은 한국거래소 코스닥시장본부 소관임
                    - 채: 본 문서는 한국거래소 채권상장법인 공시사항임
                    - 넥: 본 문서는 한국거래소 코넥스시장 소관임
                    - 공: 본 공시사항은 공정거래위원회 소관임
                    - 연: 본 보고서는 연결부분을 포함한 것임
                    - 정: 본 보고서 제출 후 정정신고가 있으니 관련 보고서를 참조하시기 바람
                    - 철: 본 보고서는 철회(간주)되었으니 관련 철회신고서(철회간주안내)를 참고하시기 바람
    """
    # 파라미터 검증
    if not api_key or len(api_key) != 40:
        raise ValueError("api_key는 40자리 인증키여야 합니다.")

    if corp_code and len(corp_code) != 8:
        raise ValueError("corp_code는 8자리 고유번호여야 합니다.")

    # 날짜 처리
    if start:
        if isinstance(start, str):
            start_dt = pd.to_datetime(start)
        else:
            start_dt = start
    else:
        start_dt = pd.to_datetime("1900-01-01")

    if end:
        if isinstance(end, str):
            end_dt = pd.to_datetime(end)
        else:
            end_dt = end
    else:
        end_dt = datetime.today()

    # 공시유형 검증
    valid_kinds = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    if kind and kind not in valid_kinds:
        raise ValueError(f"kind는 다음 중 하나여야 합니다: {', '.join(valid_kinds)}")

    # 법인구분 검증
    valid_corp_cls = ["Y", "K", "N", "E"]
    if corp_cls and corp_cls not in valid_corp_cls:
        raise ValueError(f"corp_cls는 다음 중 하나여야 합니다: {', '.join(valid_corp_cls)}")

    # 정렬 검증
    valid_sorts = ["date", "crp", "rpt"]
    if sort not in valid_sorts:
        raise ValueError(f"sort는 다음 중 하나여야 합니다: {', '.join(valid_sorts)}")

    # 정렬방법 검증
    valid_sort_mths = ["asc", "desc"]
    if sort_mth not in valid_sort_mths:
        raise ValueError(f"sort_mth는 다음 중 하나여야 합니다: {', '.join(valid_sort_mths)}")

    # 페이지 건수 검증
    if page_count < 1 or page_count > 100:
        raise ValueError("page_count는 1~100 사이의 값이어야 합니다.")

    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": start_dt.strftime("%Y%m%d"),
        "end_de": end_dt.strftime("%Y%m%d"),
        "last_reprt_at": "Y" if final else "N",
        "page_no": page_no,
        "page_count": page_count,
        "sort": sort,
        "sort_mth": sort_mth,
    }

    if kind:
        params["pblntf_ty"] = kind
    if kind_detail:
        params["pblntf_detail_ty"] = kind_detail
    if corp_cls:
        params["corp_cls"] = corp_cls

    try:
        # 첫 페이지 요청
        response = requests.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        # 에러 처리
        if "status" in data:
            status = data.get("status", "")
            message = data.get("message", "")

            error_codes = {
                "010": "등록되지 않은 키입니다",
                "011": "사용할 수 없는 키입니다. 오픈API에 등록되었으나, 일시적으로 사용 중지된 키를 통하여 검색하는 경우 발생합니다",
                "012": "접근할 수 없는 IP입니다",
                "013": "조회된 데이타가 없습니다",
                "014": "파일이 존재하지 않습니다",
                "020": "요청 제한을 초과하였습니다. 일반적으로는 20,000건 이상의 요청에 대하여 이 에러 메시지가 발생되나, 요청 제한이 다르게 설정된 경우에는 이에 준하여 발생됩니다",
                "021": "조회 가능한 회사 개수가 초과하였습니다 (최대 100건)",
                "100": "필드의 부적절한 값입니다. 필드 설명에 없는 값을 사용한 경우에 발생하는 메시지입니다",
                "101": "부적절한 접근입니다",
                "800": "시스템 점검으로 인한 서비스가 중지 중입니다",
                "900": "정의되지 않은 오류가 발생하였습니다",
                "901": "사용자 계정의 개인정보 보유기간이 만료되어 사용할 수 없는 키입니다. 관리자 이메일(opendart@fss.or.kr)로 문의하시기 바랍니다",
            }

            if status != "000":
                error_message = error_codes.get(status, message)
                raise APIError(status, error_message)

        # 모든 페이지 가져오기
        if "list" not in data:
            data["list"] = []
            return data

        all_list = data["list"].copy()
        total_page = int(data.get("total_page", 1))

        # 나머지 페이지 가져오기
        for page in range(2, total_page + 1):
            params["page_no"] = page
            response = requests.get(url, params=params)
            response.raise_for_status()

            page_data = response.json()

            if "status" in page_data and page_data["status"] != "000":
                status = page_data.get("status", "")
                message = page_data.get("message", "")
                error_codes = {
                    "010": "등록되지 않은 키입니다",
                    "011": "사용할 수 없는 키입니다. 오픈API에 등록되었으나, 일시적으로 사용 중지된 키를 통하여 검색하는 경우 발생합니다",
                    "012": "접근할 수 없는 IP입니다",
                    "013": "조회된 데이타가 없습니다",
                    "014": "파일이 존재하지 않습니다",
                    "020": "요청 제한을 초과하였습니다. 일반적으로는 20,000건 이상의 요청에 대하여 이 에러 메시지가 발생되나, 요청 제한이 다르게 설정된 경우에는 이에 준하여 발생됩니다",
                    "021": "조회 가능한 회사 개수가 초과하였습니다 (최대 100건)",
                    "100": "필드의 부적절한 값입니다. 필드 설명에 없는 값을 사용한 경우에 발생하는 메시지입니다",
                    "101": "부적절한 접근입니다",
                    "800": "시스템 점검으로 인한 서비스가 중지 중입니다",
                    "900": "정의되지 않은 오류가 발생하였습니다",
                    "901": "사용자 계정의 개인정보 보유기간이 만료되어 사용할 수 없는 키입니다. 관리자 이메일(opendart@fss.or.kr)로 문의하시기 바랍니다",
                }
                error_message = error_codes.get(status, message)
                raise APIError(status, error_message)

            if "list" in page_data:
                all_list.extend(page_data["list"])

        # 모든 페이지의 데이터를 합쳐서 반환
        data["list"] = all_list

        return data

    except requests.exceptions.RequestException as e:
        raise APIError("CONNECTION_ERROR", f"API 호출 중 네트워크 오류가 발생했습니다: {str(e)}")
    except Exception as e:
        if isinstance(e, (ValueError, APIError)):
            raise
        raise APIError("UNKNOWN_ERROR", f"예상치 못한 오류가 발생했습니다: {str(e)}")


def company(api_key: str, corp_code: str) -> Dict[str, Any]:
    """기업개황정보를 조회합니다.

    DART에 등록되어있는 기업의 개황정보를 제공합니다.

    Args:
        api_key: API 인증키. 발급받은 인증키(40자리). 필수 파라미터입니다.
        corp_code: 고유번호. 공시대상회사의 고유번호(8자리. 예: 00120182). 필수 파라미터입니다.

    Returns:
        dict: 기업개황정보를 담은 딕셔너리. 다음 구조를 가집니다:
            - status (str): 에러 및 정보 코드
            - message (str): 에러 및 정보 메시지
            - corp_name (str): 정식명칭 (정식회사명칭)
            - corp_name_eng (str): 영문명칭 (영문정식회사명칭)
            - stock_name (str): 종목명(상장사) 또는 약식명칭(기타법인)
            - stock_code (str): 상장회사인 경우 주식의 종목코드 (상장회사의 종목코드 6자리)
            - ceo_nm (str): 대표자명
            - corp_cls (str): 법인구분 (Y:유가, K:코스닥, N:코넥스, E:기타)
            - jurir_no (str): 법인등록번호
            - bizr_no (str): 사업자등록번호
            - adres (str): 주소
            - hm_url (str): 홈페이지
            - ir_url (str): IR홈페이지
            - phn_no (str): 전화번호
            - fax_no (str): 팩스번호
            - induty_code (str): 업종코드
            - est_dt (str): 설립일 (YYYYMMDD)
            - acc_mt (str): 결산월 (MM)
    """
    # 파라미터 검증
    if not api_key or len(api_key) != 40:
        raise ValueError("api_key는 40자리 인증키여야 합니다.")

    if not corp_code or len(corp_code) != 8:
        raise ValueError("corp_code는 8자리 고유번호여야 합니다.")

    url = "https://opendart.fss.or.kr/api/company.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        # 에러 처리
        if "status" in data:
            status = data.get("status", "")
            message = data.get("message", "")

            error_codes = {
                "010": "등록되지 않은 키입니다",
                "011": "사용할 수 없는 키입니다. 오픈API에 등록되었으나, 일시적으로 사용 중지된 키를 통하여 검색하는 경우 발생합니다",
                "012": "접근할 수 없는 IP입니다",
                "013": "조회된 데이타가 없습니다",
                "014": "파일이 존재하지 않습니다",
                "020": "요청 제한을 초과하였습니다. 일반적으로는 20,000건 이상의 요청에 대하여 이 에러 메시지가 발생되나, 요청 제한이 다르게 설정된 경우에는 이에 준하여 발생됩니다",
                "021": "조회 가능한 회사 개수가 초과하였습니다 (최대 100건)",
                "100": "필드의 부적절한 값입니다. 필드 설명에 없는 값을 사용한 경우에 발생하는 메시지입니다",
                "101": "부적절한 접근입니다",
                "800": "시스템 점검으로 인한 서비스가 중지 중입니다",
                "900": "정의되지 않은 오류가 발생하였습니다",
                "901": "사용자 계정의 개인정보 보유기간이 만료되어 사용할 수 없는 키입니다. 관리자 이메일(opendart@fss.or.kr)로 문의하시기 바랍니다",
            }

            if status != "000":
                error_message = error_codes.get(status, message)
                raise APIError(status, error_message)

        return data

    except requests.exceptions.RequestException as e:
        raise APIError("CONNECTION_ERROR", f"API 호출 중 네트워크 오류가 발생했습니다: {str(e)}")
    except Exception as e:
        if isinstance(e, (ValueError, APIError)):
            raise
        raise APIError("UNKNOWN_ERROR", f"예상치 못한 오류가 발생했습니다: {str(e)}")


def document(api_key: str, rcp_no: str) -> str:
    """공시서류원본파일을 조회합니다.

    공시보고서 원본파일을 제공합니다. ZIP 파일 형식으로 반환되며,
    첫 번째 파일의 XML 내용을 디코딩하여 반환합니다.

    Args:
        api_key: API 인증키. 발급받은 인증키(40자리). 필수 파라미터입니다.
        rcp_no: 접수번호. 접수번호(14자리. 예: 20190401004781). 필수 파라미터입니다.

    Returns:
        str: 공시서류원본파일의 XML 내용 (첫 번째 파일).
             인코딩은 euc-kr, utf-8 순서로 시도하며, 실패 시 바이너리 데이터를 반환합니다.
    """
    # 파라미터 검증
    if not api_key or len(api_key) != 40:
        raise ValueError("api_key는 40자리 인증키여야 합니다.")

    if not rcp_no or len(rcp_no) != 14:
        raise ValueError("rcp_no는 14자리 접수번호여야 합니다.")

    url = "https://opendart.fss.or.kr/api/document.xml"
    params = {
        "crtfc_key": api_key,
        "rcept_no": rcp_no,
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()

        # 응답이 XML 에러 메시지인지 확인
        try:
            tree = ET.XML(response.text)
            status = tree.find("status")
            message = tree.find("message")
            if status is not None and message is not None:
                status_text = status.text
                message_text = message.text

                error_codes = {
                    "010": "등록되지 않은 키입니다",
                    "011": "사용할 수 없는 키입니다. 오픈API에 등록되었으나, 일시적으로 사용 중지된 키를 통하여 검색하는 경우 발생합니다",
                    "012": "접근할 수 없는 IP입니다",
                    "013": "조회된 데이타가 없습니다",
                    "014": "파일이 존재하지 않습니다",
                    "020": "요청 제한을 초과하였습니다. 일반적으로는 20,000건 이상의 요청에 대하여 이 에러 메시지가 발생되나, 요청 제한이 다르게 설정된 경우에는 이에 준하여 발생됩니다",
                    "021": "조회 가능한 회사 개수가 초과하였습니다 (최대 100건)",
                    "100": "필드의 부적절한 값입니다. 필드 설명에 없는 값을 사용한 경우에 발생하는 메시지입니다",
                    "101": "부적절한 접근입니다",
                    "800": "시스템 점검으로 인한 서비스가 중지 중입니다",
                    "900": "정의되지 않은 오류가 발생하였습니다",
                    "901": "사용자 계정의 개인정보 보유기간이 만료되어 사용할 수 없는 키입니다. 관리자 이메일(opendart@fss.or.kr)로 문의하시기 바랍니다",
                }

                if status_text != "000":
                    error_message = error_codes.get(status_text, message_text)
                    raise APIError(status_text, error_message)
        except ET.ParseError:
            # XML 파싱 실패 시 ZIP 파일로 간주하고 계속 진행
            pass

        # ZIP 파일 처리
        zf = zipfile.ZipFile(io.BytesIO(response.content))
        info_list = zf.infolist()

        if not info_list:
            raise APIError("NO_FILE", "ZIP 파일에 포함된 파일이 없습니다.")

        fnames = sorted([info.filename for info in info_list])
        xml_data = zf.read(fnames[0])

        # 인코딩 시도
        try:
            xml_text = xml_data.decode("euc-kr")
        except UnicodeDecodeError:
            try:
                xml_text = xml_data.decode("utf-8")
            except UnicodeDecodeError:
                # 인코딩 실패 시 바이너리 데이터를 문자열로 변환
                xml_text = xml_data

        try:
            parsed_text = parse_dart_to_text(xml_text)
        except Exception:
            parsed_text = xml_text

        return parsed_text

    except requests.exceptions.RequestException as e:
        raise APIError("CONNECTION_ERROR", f"API 호출 중 네트워크 오류가 발생했습니다: {str(e)}")
    except zipfile.BadZipFile as e:
        raise APIError("INVALID_ZIP", f"유효하지 않은 ZIP 파일입니다: {str(e)}")
    except Exception as e:
        if isinstance(e, (ValueError, APIError)):
            raise
        raise APIError("UNKNOWN_ERROR", f"예상치 못한 오류가 발생했습니다: {str(e)}")


def corpCode(api_key: str) -> Dict[str, Any]:
    """공시대상회사의 고유번호 정보를 조회합니다.

    DART에 등록되어있는 공시대상회사의 고유번호, 회사명, 종목코드, 최근변경일자를 파일로 제공합니다.
    ZIP 파일 형식으로 반환되며, 내부 XML 파일을 파싱하여 정보를 추출합니다.

    Args:
        api_key: API 인증키. 발급받은 인증키(40자리). 필수 파라미터입니다.

    Returns:
        dict: 공시대상회사 정보를 담은 딕셔너리. 다음 구조를 가집니다:
            - status (str): 에러 및 정보 코드
            - message (str): 에러 및 정보 메시지
            - list (list): 공시대상회사 정보 배열. 각 항목은 다음 필드를 포함:
                - corp_code (str): 고유번호 (공시대상회사의 고유번호 8자리)
                - corp_name (str): 정식명칭 (정식회사명칭)
                - corp_eng_name (str): 영문 정식명칭 (영문정식회사명칭)
                - stock_code (str): 종목코드 (상장회사인 경우 주식의 종목코드 6자리)
                - modify_date (str): 최종변경일자 (기업개황정보 최종변경일자 YYYYMMDD)
    """
    # 파라미터 검증
    if not api_key or len(api_key) != 40:
        raise ValueError("api_key는 40자리 인증키여야 합니다.")

    url = "https://opendart.fss.or.kr/api/corpCode.xml"
    params = {
        "crtfc_key": api_key,
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()

        # 응답이 XML 에러 메시지인지 확인
        try:
            tree = ET.XML(response.content)
            status = tree.find("status")
            message = tree.find("message")
            if status is not None and message is not None:
                status_text = status.text
                message_text = message.text

                error_codes = {
                    "010": "등록되지 않은 키입니다",
                    "011": "사용할 수 없는 키입니다. 오픈API에 등록되었으나, 일시적으로 사용 중지된 키를 통하여 검색하는 경우 발생합니다",
                    "012": "접근할 수 없는 IP입니다",
                    "013": "조회된 데이타가 없습니다",
                    "014": "파일이 존재하지 않습니다",
                    "020": "요청 제한을 초과하였습니다. 일반적으로는 20,000건 이상의 요청에 대하여 이 에러 메시지가 발생되나, 요청 제한이 다르게 설정된 경우에는 이에 준하여 발생됩니다",
                    "021": "조회 가능한 회사 개수가 초과하였습니다 (최대 100건)",
                    "100": "필드의 부적절한 값입니다. 필드 설명에 없는 값을 사용한 경우에 발생하는 메시지입니다",
                    "101": "부적절한 접근입니다",
                    "800": "시스템 점검으로 인한 서비스가 중지 중입니다",
                    "900": "정의되지 않은 오류가 발생하였습니다",
                    "901": "사용자 계정의 개인정보 보유기간이 만료되어 사용할 수 없는 키입니다. 관리자 이메일(opendart@fss.or.kr)로 문의하시기 바랍니다",
                }

                if status_text != "000":
                    error_message = error_codes.get(status_text, message_text)
                    raise APIError(status_text, error_message)
        except ET.ParseError:
            # XML 파싱 실패 시 ZIP 파일로 간주하고 계속 진행
            pass

        # ZIP 파일 처리
        zf = zipfile.ZipFile(io.BytesIO(response.content))

        try:
            xml_data = zf.read("CORPCODE.xml")
        except KeyError:
            # CORPCODE.xml 파일이 없는 경우 다른 파일명 시도
            info_list = zf.infolist()
            if not info_list:
                raise APIError("NO_FILE", "ZIP 파일에 포함된 파일이 없습니다.")
            xml_data = zf.read(info_list[0].filename)

        # XML 파싱
        tree = ET.XML(xml_data)
        all_records = []

        element = tree.findall("list")
        for child in element:
            record = {}
            for subchild in child:
                record[subchild.tag] = subchild.text
            all_records.append(record)

        return {"status": "000", "message": "정상", "list": all_records}

    except requests.exceptions.RequestException as e:
        raise APIError("CONNECTION_ERROR", f"API 호출 중 네트워크 오류가 발생했습니다: {str(e)}")
    except zipfile.BadZipFile as e:
        raise APIError("INVALID_ZIP", f"유효하지 않은 ZIP 파일입니다: {str(e)}")
    except Exception as e:
        if isinstance(e, (ValueError, APIError)):
            raise
        raise APIError("UNKNOWN_ERROR", f"예상치 못한 오류가 발생했습니다: {str(e)}")
