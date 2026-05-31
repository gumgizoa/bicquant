from datetime import datetime
from typing import Any, Dict, Optional, Union

import requests

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
    api_key: str,
    corp_code: str,
    start: Optional[Union[str, datetime]] = None,
    end: Optional[Union[str, datetime]] = None,
) -> Dict[str, Any]:
    """주식등의 대량보유상황보고서 정보를 조회합니다.

    주식등의 대량보유상황보고서 내에 대량보유 상황보고 정보를 제공합니다.

    Args:
        api_key: API 인증키. 발급받은 인증키(40자리). 필수 파라미터입니다.
        corp_code: 고유번호. 공시대상회사의 고유번호(8자리. 예: 00126380). 필수 파라미터입니다.
        start: 시작일. 검색 시작 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.
        end: 종료일. 검색 종료 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.

    Returns:
        dict: 대량보유 상황보고 정보를 담은 딕셔너리. 다음 구조를 가집니다:
            - status (str): 에러 및 정보 코드
            - message (str): 에러 및 정보 메시지
            - list (list): 대량보유 상황보고 정보 배열. 각 항목은 다음 필드를 포함:
                - rcept_no (str): 접수번호(14자리). 접수번호(rcept_no)를 이용하여 공시뷰어에 접근할 수 있습니다.
                - rcept_dt (str): 접수일자 (공시 접수일자 YYYY-MM-DD)
                - corp_code (str): 고유번호 (공시대상회사의 고유번호 8자리)
                - corp_name (str): 회사명 (공시대상회사의 종목명(상장사) 또는 법인명(기타법인))
                - report_tp (str): 보고구분 (주식등의 대량보유상황 보고구분)
                - repror (str): 대표보고자
                - stkqy (str): 보유주식등의 수
                - stkqy_irds (str): 보유주식등의 증감
                - stkrt (str): 보유비율
                - stkrt_irds (str): 보유비율 증감
                - ctr_stkqy (str): 주요체결 주식등의 수
                - ctr_stkrt (str): 주요체결 보유비율
                - report_resn (str): 보고사유
    """
    # 파라미터 검증
    if not api_key or len(api_key) != 40:
        raise ValueError("api_key는 40자리 인증키여야 합니다.")

    if not corp_code or len(corp_code) != 8:
        raise ValueError("corp_code는 8자리 고유번호여야 합니다.")

    start_dt = _parse_date_param(start, "start")
    end_dt = _parse_date_param(end, "end")

    if start_dt and end_dt and start_dt > end_dt:
        raise ValueError(f"start({start_dt.strftime('%Y%m%d')})는 end({end_dt.strftime('%Y%m%d')})보다 작거나 같아야 합니다.")

    url = "https://opendart.fss.or.kr/api/majorstock.json"
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

        # rcept_dt(YYYY-MM-DD) 기준 후처리 필터링
        data = _filter_by_rcept_dt(data, start_dt, end_dt, "%Y-%m-%d")

        return data

    except requests.exceptions.RequestException as e:
        raise APIError("CONNECTION_ERROR", f"API 호출 중 네트워크 오류가 발생했습니다: {str(e)}")
    except Exception as e:
        if isinstance(e, (ValueError, APIError)):
            raise
        raise APIError("UNKNOWN_ERROR", f"예상치 못한 오류가 발생했습니다: {str(e)}")


def elestock(
    api_key: str,
    corp_code: str,
    start: Optional[Union[str, datetime]] = None,
    end: Optional[Union[str, datetime]] = None,
) -> Dict[str, Any]:
    """임원ㆍ주요주주특정증권등 소유상황보고서 정보를 조회합니다.

    임원ㆍ주요주주특정증권등 소유상황보고서 내에 임원ㆍ주요주주 소유보고 정보를 제공합니다.

    Args:
        api_key: API 인증키. 발급받은 인증키(40자리). 필수 파라미터입니다.
        corp_code: 고유번호. 공시대상회사의 고유번호(8자리. 예: 00126380). 필수 파라미터입니다.
        start: 시작일. 검색 시작 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.
        end: 종료일. 검색 종료 접수일자(YYYYMMDD 형식 문자열 또는 datetime 객체). 선택 파라미터입니다.

    Returns:
        dict: 임원ㆍ주요주주 소유보고 정보를 담은 딕셔너리. 다음 구조를 가집니다:
            - status (str): 에러 및 정보 코드
            - message (str): 에러 및 정보 메시지
            - list (list): 임원ㆍ주요주주 소유보고 정보 배열. 각 항목은 다음 필드를 포함:
                - rcept_no (str): 접수번호(14자리). 접수번호(rcept_no)를 이용하여 공시뷰어에 접근할 수 있습니다.
                - rcept_dt (str): 접수일자 (공시 접수일자 YYYY-MM-DD)
                - corp_code (str): 고유번호 (공시대상회사의 고유번호 8자리)
                - corp_name (str): 회사명
                - repror (str): 보고자명
                - isu_exctv_rgist_at (str): 발행 회사 관계 임원(등기여부) (등기임원, 비등기임원 등)
                - isu_exctv_ofcps (str): 발행 회사 관계 임원 직위 (대표이사, 이사, 전무 등)
                - isu_main_shrholdr (str): 발행 회사 관계 주요 주주 (10%이상주주 등)
                - sp_stock_lmp_cnt (str): 특정 증권 등 소유 수
                - sp_stock_lmp_irds_cnt (str): 특정 증권 등 소유 증감 수
                - sp_stock_lmp_rate (str): 특정 증권 등 소유 비율
                - sp_stock_lmp_irds_rate (str): 특정 증권 등 소유 증감 비율
    """
    # 파라미터 검증
    if not api_key or len(api_key) != 40:
        raise ValueError("api_key는 40자리 인증키여야 합니다.")

    if not corp_code or len(corp_code) != 8:
        raise ValueError("corp_code는 8자리 고유번호여야 합니다.")

    start_dt = _parse_date_param(start, "start")
    end_dt = _parse_date_param(end, "end")

    if start_dt and end_dt and start_dt > end_dt:
        raise ValueError(f"start({start_dt.strftime('%Y%m%d')})는 end({end_dt.strftime('%Y%m%d')})보다 작거나 같아야 합니다.")

    url = "https://opendart.fss.or.kr/api/elestock.json"
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

        # rcept_dt(YYYY-MM-DD) 기준 후처리 필터링
        data = _filter_by_rcept_dt(data, start_dt, end_dt, "%Y-%m-%d")

        return data

    except requests.exceptions.RequestException as e:
        raise APIError("CONNECTION_ERROR", f"API 호출 중 네트워크 오류가 발생했습니다: {str(e)}")
    except Exception as e:
        if isinstance(e, (ValueError, APIError)):
            raise
        raise APIError("UNKNOWN_ERROR", f"예상치 못한 오류가 발생했습니다: {str(e)}")
