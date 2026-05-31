# -*- coding:utf-8 -*-

from datetime import datetime
from typing import Any, Dict, Optional, Union

import pandas as pd
import requests

from dartapi.dart_catalog import EVENT_CATALOG
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


def _call_event_api(
    api_key: str,
    corp_code: str,
    endpoint: str,
    start: Optional[Union[str, datetime]] = None,
    end: Optional[Union[str, datetime]] = None,
) -> Dict[str, Any]:
    if not api_key or len(api_key) != 40:
        raise ValueError("api_key는 40자리 인증키여야 합니다.")

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
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": start_dt.strftime("%Y%m%d"),
        "end_de": end_dt.strftime("%Y%m%d"),
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


def event(
    api_key: str,
    corp_code: str,
    event_type: str,
    start: Optional[Union[str, datetime]] = None,
    end: Optional[Union[str, datetime]] = None,
) -> Dict[str, Any]:
    """주요사항보고서 이벤트를 조회합니다.

    Args:
        api_key: API 인증키. 발급받은 인증키(40자리). 필수 파라미터입니다.
        corp_code: 고유번호. 공시대상회사의 고유번호(8자리. 예: 00126380). 필수 파라미터입니다.
        event_type: 이벤트 유형(API 엔드포인트 이름). 사용 가능한 값은 dart_catalog.EVENT_CATALOG 참조.
                    예: "piicDecsn", "cvbdIsDecsn", "tsstkAqDecsn"
        start: 시작일. 검색시작 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.
        end: 종료일. 검색종료 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.

    Returns:
        dict: 이벤트 정보를 담은 딕셔너리. 다음 공통 구조를 가집니다:
            - status (str): 에러 및 정보 코드
            - message (str): 에러 및 정보 메시지
            - list (list): 이벤트 정보 배열. 필드는 event_type에 따라 다름.
                           dart_catalog.EVENT_CATALOG[event_type]["fields"]에서 필드별 상세 설명 확인 가능.

    Raises:
        ValueError: event_type이 EVENT_CATALOG에 없는 경우.
    """
    if event_type not in EVENT_CATALOG:
        valid = sorted(EVENT_CATALOG.keys())
        raise ValueError(f"Unknown event_type: {event_type!r}. Valid values: {valid}")
    return _call_event_api(api_key, corp_code, event_type, start, end)
