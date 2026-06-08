# -*- coding:utf-8 -*-

from datetime import datetime
from typing import Any, Dict, Optional, Union

import httpx
import pandas as pd

from dartapi._http import raise_for_dart_status
from dartapi.dart_catalog import REGSTATE_RETURN_FIELDS_CATALOG
from dartapi.exceptions import APIError


def _call_regstate_api(
    client: httpx.Client,
    corp_code: str,
    endpoint: str,
    start: Optional[Union[str, datetime]] = None,
    end: Optional[Union[str, datetime]] = None,
) -> Dict[str, Any]:
    if not corp_code or len(corp_code) != 8:
        raise ValueError("corp_code는 8자리 고유번호여야 합니다.")

    start_dt = pd.to_datetime(start) if start else pd.to_datetime("1900-01-01")
    end_dt = pd.to_datetime(end) if end else datetime.today()

    try:
        if start_dt.year < 2015 or end_dt.year < 2015:
            raise ValueError("2015년 이후부터 정보제공됩니다.")
    except (AttributeError, ValueError):
        pass

    url = f"https://opendart.fss.or.kr/api/{endpoint}.json"
    params = {
        "corp_code": corp_code,
        "bgn_de": start_dt.strftime("%Y%m%d"),
        "end_de": end_dt.strftime("%Y%m%d"),
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


def regstate(
    client: httpx.Client,
    corp_code: str,
    report_type: str,
    start: Optional[Union[str, datetime]] = None,
    end: Optional[Union[str, datetime]] = None,
) -> Dict[str, Any]:
    """증권신고서 정보를 조회합니다.

    Args:
        client: crtfc_key가 설정된 httpx.Client (DartServerState.get_client() 참조).
        corp_code: 고유번호. 공시대상회사의 고유번호(8자리. 예: 00126380). 필수 파라미터입니다.
        report_type: 신고서 유형(API 엔드포인트 이름). 사용 가능한 값은 dart_catalog.REGSTATE_RETURN_FIELDS_CATALOG 참조.
                     예: "estkRs", "bdRs", "mgRs"
        start: 시작일. 검색시작 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.
        end: 종료일. 검색종료 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.
    """
    if report_type not in REGSTATE_RETURN_FIELDS_CATALOG:
        valid = sorted(REGSTATE_RETURN_FIELDS_CATALOG.keys())
        raise ValueError(f"Unknown report_type: {report_type!r}. Valid values: {valid}")
    return _call_regstate_api(client, corp_code, report_type, start, end)
