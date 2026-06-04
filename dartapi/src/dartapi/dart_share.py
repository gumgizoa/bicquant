from datetime import datetime
from typing import Any, Dict, Optional, Union

import httpx

from dartapi._http import raise_for_dart_status
from dartapi.exceptions import APIError


def _parse_date_param(date: Optional[Union[str, datetime]], param_name: str) -> Optional[datetime]:
    """날짜 파라미터를 datetime으로 변환합니다.

    Args:
        date: YYYYMMDD 형식 문자열 또는 datetime 객체, 또는 None
        param_name: 파라미터 이름 (에러 메시지용)
    """
    if date is None:
        return None

    if isinstance(date, datetime):
        return date

    if isinstance(date, str):
        try:
            # YYYYMMDD 형식 강제
            return datetime.strptime(date, "%Y%m%d")
        except ValueError as e:
            raise ValueError(f"datetime.strptime({date}) 오류: {e}")

    raise ValueError(f"{param_name}는 YYYYMMDD 형식 문자열 또는 datetime 객체여야 합니다: {date}")


def _filter_by_rcept_dt(
    data: Dict[str, Any],
    start: Optional[datetime],
    end: Optional[datetime],
    date_format: str,
) -> Dict[str, Any]:
    """rcept_dt 기반으로 data['list']를 필터링합니다."""
    if "list" not in data or not isinstance(data["list"], list):
        return data

    if start is None and end is None:
        return data

    filtered_list = []
    for item in data["list"]:
        rcept_dt_raw = item.get("rcept_dt")
        if not rcept_dt_raw:
            continue

        try:
            # majorstock과 elestock 모두 YYYY-MM-DD 형식이므로 포맷에 맞게 파싱
            rcept_dt = datetime.strptime(rcept_dt_raw, date_format)
        except ValueError:
            # rcept_dt 형식이 예상과 다르면 스킵
            continue

        if start and rcept_dt < start:
            continue
        if end and rcept_dt > end:
            continue

        filtered_list.append(item)

    data["list"] = filtered_list
    return data


def majorstock(
    client: httpx.Client,
    corp_code: str,
    start: Optional[Union[str, datetime]] = None,
    end: Optional[Union[str, datetime]] = None,
) -> Dict[str, Any]:
    """주식등의 대량보유상황보고서 정보를 조회합니다.

    주식등의 대량보유상황보고서 내에 대량보유 상황보고 정보를 제공합니다.

    Args:
        client: crtfc_key가 설정된 httpx.Client (DartServerState.get_client() 참조).
        corp_code: 고유번호. 공시대상회사의 고유번호(8자리. 예: 00126380). 필수 파라미터입니다.
        start: 시작일. 검색 시작 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.
        end: 종료일. 검색 종료 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.
    """
    # 파라미터 검증
    if not corp_code or len(corp_code) != 8:
        raise ValueError("corp_code는 8자리 고유번호여야 합니다.")

    start_dt = _parse_date_param(start, "start")
    end_dt = _parse_date_param(end, "end")

    if start_dt and end_dt and start_dt > end_dt:
        raise ValueError(f"start({start_dt.strftime('%Y%m%d')})는 end({end_dt.strftime('%Y%m%d')})보다 작거나 같아야 합니다.")

    url = "https://opendart.fss.or.kr/api/majorstock.json"
    params = {
        "corp_code": corp_code,
    }

    try:
        response = client.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        # 에러 처리
        raise_for_dart_status(data)

        # rcept_dt(YYYY-MM-DD) 기준 후처리 필터링
        data = _filter_by_rcept_dt(data, start_dt, end_dt, "%Y-%m-%d")

        return data

    except httpx.HTTPError as e:
        raise APIError("CONNECTION_ERROR", f"API 호출 중 네트워크 오류가 발생했습니다: {str(e)}")
    except Exception as e:
        if isinstance(e, (ValueError, APIError)):
            raise
        raise APIError("UNKNOWN_ERROR", f"예상치 못한 오류가 발생했습니다: {str(e)}")


def elestock(
    client: httpx.Client,
    corp_code: str,
    start: Optional[Union[str, datetime]] = None,
    end: Optional[Union[str, datetime]] = None,
) -> Dict[str, Any]:
    """임원ㆍ주요주주특정증권등 소유상황보고서 정보를 조회합니다.

    임원ㆍ주요주주특정증권등 소유상황보고서 내에 임원ㆍ주요주주 소유보고 정보를 제공합니다.

    Args:
        client: crtfc_key가 설정된 httpx.Client (DartServerState.get_client() 참조).
        corp_code: 고유번호. 공시대상회사의 고유번호(8자리. 예: 00126380). 필수 파라미터입니다.
        start: 시작일. 검색 시작 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.
        end: 종료일. 검색 종료 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.
    """
    # 파라미터 검증
    if not corp_code or len(corp_code) != 8:
        raise ValueError("corp_code는 8자리 고유번호여야 합니다.")

    start_dt = _parse_date_param(start, "start")
    end_dt = _parse_date_param(end, "end")

    if start_dt and end_dt and start_dt > end_dt:
        raise ValueError(f"start({start_dt.strftime('%Y%m%d')})는 end({end_dt.strftime('%Y%m%d')})보다 작거나 같아야 합니다.")

    url = "https://opendart.fss.or.kr/api/elestock.json"
    params = {
        "corp_code": corp_code,
    }

    try:
        response = client.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        # 에러 처리
        raise_for_dart_status(data)

        # rcept_dt(YYYY-MM-DD) 기준 후처리 필터링
        data = _filter_by_rcept_dt(data, start_dt, end_dt, "%Y-%m-%d")

        return data

    except httpx.HTTPError as e:
        raise APIError("CONNECTION_ERROR", f"API 호출 중 네트워크 오류가 발생했습니다: {str(e)}")
    except Exception as e:
        if isinstance(e, (ValueError, APIError)):
            raise
        raise APIError("UNKNOWN_ERROR", f"예상치 못한 오류가 발생했습니다: {str(e)}")
