# -*- coding:utf-8 -*-

from typing import Any, Dict, Union

import requests

from dartapi.dart_catalog import REPORT_CATALOG
from dartapi.exceptions import APIError

_ERROR_CODES = {
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


def _call_report_api(
    api_key: str,
    corp_code: str,
    endpoint: str,
    bsns_year: Union[str, int],
    reprt_code: str = "11011",
) -> Dict[str, Any]:
    if not api_key or len(api_key) != 40:
        raise ValueError("api_key는 40자리 인증키여야 합니다.")

    if not corp_code or len(corp_code) != 8:
        raise ValueError("corp_code는 8자리 고유번호여야 합니다.")

    bsns_year_str = str(bsns_year)
    if len(bsns_year_str) != 4:
        raise ValueError("bsns_year는 4자리여야 합니다.")

    try:
        if int(bsns_year_str) < 2015:
            raise ValueError("2015년 이후부터 정보제공됩니다.")
    except ValueError:
        raise ValueError("bsns_year는 숫자여야 합니다.")

    valid_reprt_codes = ["11011", "11012", "11013", "11014"]
    if reprt_code not in valid_reprt_codes:
        raise ValueError(f"reprt_code는 다음 중 하나여야 합니다: {', '.join(valid_reprt_codes)}")

    url = f"https://opendart.fss.or.kr/api/{endpoint}.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year_str,
        "reprt_code": reprt_code,
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if "status" in data:
            status = data.get("status", "")
            if status != "000":
                raise APIError(status, _ERROR_CODES.get(status, data.get("message", "")))

        return data

    except requests.exceptions.RequestException as e:
        raise APIError("CONNECTION_ERROR", f"API 호출 중 네트워크 오류가 발생했습니다: {str(e)}")
    except Exception as e:
        if isinstance(e, (ValueError, APIError)):
            raise
        raise APIError("UNKNOWN_ERROR", f"예상치 못한 오류가 발생했습니다: {str(e)}")


def report(
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
        report_type: 조회 항목(API 엔드포인트 이름). 사용 가능한 값은 dart_catalog.REPORT_CATALOG 참조.
                     예: "irdsSttus", "exctvSttus", "empSttus"
        bsns_year: 사업연도. 사업연도(4자리). 2015년 이후부터 정보제공됩니다. 필수 파라미터입니다.
        reprt_code: 보고서 코드. 선택 파라미터입니다. 다음 중 하나를 선택할 수 있습니다:
                    - "11013": 1분기보고서
                    - "11012": 반기보고서
                    - "11014": 3분기보고서
                    - "11011": 사업보고서 (기본값)

    Returns:
        dict: 정보를 담은 딕셔너리. 다음 공통 구조를 가집니다:
            - status (str): 에러 및 정보 코드
            - message (str): 에러 및 정보 메시지
            - list (list): 정보 배열. 필드는 report_type에 따라 다름.
                           dart_catalog.REPORT_CATALOG[report_type]["fields"]에서 필드별 상세 설명 확인 가능.

    Raises:
        ValueError: report_type이 REPORT_CATALOG에 없는 경우.
    """
    if report_type not in REPORT_CATALOG:
        valid = sorted(REPORT_CATALOG.keys())
        raise ValueError(f"Unknown report_type: {report_type!r}. Valid values: {valid}")
    return _call_report_api(api_key, corp_code, report_type, bsns_year, reprt_code)
