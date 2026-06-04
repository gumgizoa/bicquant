# -*- coding:utf-8 -*-

from typing import Any, Dict, Union

import httpx

from dartapi._http import raise_for_dart_status
from dartapi.dart_catalog import REPORT_RETURN_FIELDS_CATALOG
from dartapi.exceptions import APIError


def _call_report_api(
    client: httpx.Client,
    corp_code: str,
    endpoint: str,
    bsns_year: Union[str, int],
    reprt_code: str = "11011",
) -> Dict[str, Any]:
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
        "corp_code": corp_code,
        "bsns_year": bsns_year_str,
        "reprt_code": reprt_code,
    }

    try:
        response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        raise_for_dart_status(data)

        return data

    except httpx.HTTPError as e:
        raise APIError("CONNECTION_ERROR", f"API 호출 중 네트워크 오류가 발생했습니다: {str(e)}")
    except Exception as e:
        if isinstance(e, (ValueError, APIError)):
            raise
        raise APIError("UNKNOWN_ERROR", f"예상치 못한 오류가 발생했습니다: {str(e)}")


def report(
    client: httpx.Client,
    corp_code: str,
    report_type: str,
    bsns_year: Union[str, int],
    reprt_code: str = "11011",
) -> Dict[str, Any]:
    """정기보고서(사업/분기/반기보고서) 내 세부 항목을 조회합니다.

    Args:
        client: crtfc_key가 설정된 httpx.Client (DartServerState.get_client() 참조).
        corp_code: 고유번호. 공시대상회사의 고유번호(8자리. 예: 00126380). 필수 파라미터입니다.
        report_type: 조회 항목(API 엔드포인트 이름). 사용 가능한 값은 dart_catalog.REPORT_RETURN_FIELDS_CATALOG 참조.
                     예: "irdsSttus", "exctvSttus", "empSttus"
        bsns_year: 사업연도. 사업연도(4자리). 2015년 이후부터 정보제공됩니다. 필수 파라미터입니다.
        reprt_code: 보고서 코드. 선택 파라미터입니다. 다음 중 하나를 선택할 수 있습니다:
                    - "11013": 1분기보고서
                    - "11012": 반기보고서
                    - "11014": 3분기보고서
                    - "11011": 사업보고서 (기본값)
    """
    if report_type not in REPORT_RETURN_FIELDS_CATALOG:
        valid = sorted(REPORT_RETURN_FIELDS_CATALOG.keys())
        raise ValueError(f"Unknown report_type: {report_type!r}. Valid values: {valid}")
    return _call_report_api(client, corp_code, report_type, bsns_year, reprt_code)
