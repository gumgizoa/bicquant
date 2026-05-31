# -*- coding:utf-8 -*-
# 2020 FinanceData.KR http://financedata.kr fb.com/financedata

from typing import Any, Dict, Optional, Union

import requests

from dartapi.exceptions import APIError


def fnlttAcnt(
    api_key: str,
    corp_code: str,
    bsns_year: Union[str, int],
    reprt_code: str = "11011",
    fs_div: str = "CFS",
    sj_div: Optional[str] = None,
) -> Dict[str, Any]:
    """상장기업 재무정보(주요계정)를 조회합니다.

    상장법인(유가증권, 코스닥) 및 주요 비상장법인(사업보고서 제출대상 & IFRS 적용)이
    제출한 정기보고서 내에 XBRL재무제표의 주요계정과목(재무상태표, 손익계산서)을 제공합니다.

    단일회사 조회와 다중회사 조회를 자동으로 구분합니다:
    - 단일회사: corp_code에 콤마(,)가 없는 경우 → fnlttSinglAcnt.json 호출
    - 다중회사: corp_code에 콤마(,)로 구분된 여러 회사 코드가 있는 경우 → fnlttMultiAcnt.json 호출
      (최대 100건까지 조회 가능)

    Args:
        api_key: API 인증키. 발급받은 인증키(40자리). 필수 파라미터입니다.
        corp_code: 고유번호. 공시대상회사의 고유번호(8자리). 필수 파라미터입니다.
                  단일회사: "00126380" 형식
                  다중회사: "00334624,00126380" 형식 (콤마로 구분, 최대 100건). 다중회사 조회 시 최대 100건까지 조회 가능합니다.
        bsns_year: 사업연도. 사업연도(4자리). 2015년 이후부터 정보제공됩니다. 필수 파라미터입니다.
        reprt_code: 보고서 코드. 선택 파라미터입니다. 다음 중 하나를 선택할 수 있습니다:
                    - "11013": 1분기보고서
                    - "11012": 반기보고서
                    - "11014": 3분기보고서
                    - "11011": 사업보고서 (기본값)
        fs_div: 개별/연결구분. 선택 파라미터입니다. 다음 중 하나를 선택할 수 있습니다:
                - "OFS": 재무제표 (별도/개별)
                - "CFS": 연결재무제표 (기본값)
        sj_div: 재무제표구분 필터. 선택적 파라미터입니다. 지정하면 해당 재무제표구분의 데이터만 반환됩니다.
                다음 중 하나를 선택할 수 있습니다:
                - "BS": 재무상태표
                - "IS(CIS)": 손익계산서(포괄손익계산서)
                - "CF": 현금흐름표
                - "SCE": 자본변동표
                None인 경우 모든 재무제표구분의 데이터를 반환합니다 (기본값).

    Returns:
        dict: 재무정보를 담은 딕셔너리. 다음 구조를 가집니다:
            - status (str): 에러 및 정보 코드
            - message (str): 에러 및 정보 메시지
            - list (list): 재무정보 배열. sj_div가 지정된 경우 해당 재무제표구분의 데이터만 포함됩니다.
                          각 항목은 다음 필드를 포함:
                - rcept_no (str): 접수번호(14자리). 접수번호(rcept_no)를 이용하여 공시뷰어에 접근할 수 있습니다.
                - bsns_year (str): 사업 연도
                - stock_code (str): 종목 코드 (상장회사의 종목코드 6자리)
                - reprt_code (str): 보고서 코드
                - account_nm (str): 계정명 (예: 자본총계)
                - fs_div (str): 개별/연결구분 (OFS:재무제표, CFS:연결재무제표)
                - fs_nm (str): 개별/연결명 (예: 연결재무제표 또는 재무제표)
                - sj_div (str): 재무제표구분 (BS:재무상태표, IS:손익계산서, CIS:포괄손익계산서, CF:현금흐름표, SCE:자본변동표)
                - sj_nm (str): 재무제표명 (예: 재무상태표 또는 손익계산서)
                - thstrm_nm (str): 당기명 (예: 제 13 기 3분기말)
                - thstrm_dt (str): 당기일자 (예: 2018.09.30 현재)
                - thstrm_amount (str): 당기금액
                - thstrm_add_amount (str): 당기누적금액
                - frmtrm_nm (str): 전기명 (예: 제 12 기말)
                - frmtrm_dt (str): 전기일자 (예: 2017.01.01 ~ 2017.12.31)
                - frmtrm_amount (str): 전기금액
                - frmtrm_add_amount (str): 전기누적금액
                - bfefrmtrm_nm (str): 전전기명 (사업보고서의 경우에만 출력)
                - bfefrmtrm_dt (str): 전전기일자 (사업보고서의 경우에만 출력)
                - bfefrmtrm_amount (str): 전전기금액 (사업보고서의 경우에만 출력)
                - ord (str): 계정과목 정렬순서
                - currency (str): 통화 단위
    """
    # 파라미터 검증
    if not api_key or len(api_key) != 40:
        raise ValueError("api_key는 40자리 인증키여야 합니다.")

    if not corp_code:
        raise ValueError("corp_code는 필수 파라미터입니다.")

    # 다중회사 조회 시 회사 개수 확인
    if "," in corp_code:
        corp_codes = [code.strip() for code in corp_code.split(",")]
        if len(corp_codes) > 100:
            raise ValueError("조회 가능한 회사 개수는 최대 100건입니다.")
        for code in corp_codes:
            if len(code) != 8:
                raise ValueError(f"고유번호는 8자리여야 합니다: {code}")
    else:
        if len(corp_code) != 8:
            raise ValueError("고유번호는 8자리여야 합니다.")

    # 사업연도 검증
    bsns_year_str = str(bsns_year)
    if len(bsns_year_str) != 4:
        raise ValueError("bsns_year는 4자리여야 합니다.")

    try:
        bsns_year_int = int(bsns_year_str)
        if bsns_year_int < 2015:
            raise ValueError("전자공시의 재무데이터는 2015년 이후 데이터를 제공합니다.")
    except ValueError:
        raise ValueError("bsns_year는 숫자여야 합니다.")

    # 보고서 코드 검증
    valid_reprt_codes = ["11011", "11012", "11013", "11014"]
    if reprt_code not in valid_reprt_codes:
        raise ValueError(f"reprt_code는 다음 중 하나여야 합니다: {', '.join(valid_reprt_codes)}")

    # 개별/연결구분 검증
    valid_fs_divs = ["OFS", "CFS"]
    if fs_div not in valid_fs_divs:
        raise ValueError(f"fs_div는 다음 중 하나여야 합니다: {', '.join(valid_fs_divs)}")

    # 재무제표구분 필터 검증
    if sj_div is not None:
        valid_sj_divs = ["BS", "CIS", "IS", "CF", "SCE"]
        if sj_div not in valid_sj_divs:
            raise ValueError(f"sj_div는 다음 중 하나여야 합니다: {', '.join(valid_sj_divs)}")

    # URL 결정 (단일/다중 자동 구분)
    base_url = "https://opendart.fss.or.kr/api/"
    if "," in corp_code:
        url = base_url + "fnlttMultiAcnt.json"
    else:
        url = base_url + "fnlttSinglAcnt.json"

    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year_str,
        "reprt_code": reprt_code,
        "fs_div": fs_div,
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

        # sj_div 필터링 적용
        if sj_div is not None and "list" in data and isinstance(data["list"], list):
            data["list"] = [item for item in data["list"] if item.get("sj_div") == sj_div]

        if fs_div is not None and "list" in data and isinstance(data["list"], list):
            data["list"] = [item for item in data["list"] if item.get("fs_div") == fs_div]

        return data

    except requests.exceptions.RequestException as e:
        raise APIError("CONNECTION_ERROR", f"API 호출 중 네트워크 오류가 발생했습니다: {str(e)}")
    except Exception as e:
        if isinstance(e, (ValueError, APIError)):
            raise
        raise APIError("UNKNOWN_ERROR", f"예상치 못한 오류가 발생했습니다: {str(e)}")


def fnlttSinglAcntAll(
    api_key: str,
    corp_code: str,
    bsns_year: Union[str, int],
    reprt_code: str = "11011",
    fs_div: str = "CFS",
    sj_div: Optional[str] = None,
) -> Dict[str, Any]:
    """단일회사 전체 재무제표를 조회합니다.

    상장법인(유가증권, 코스닥) 및 주요 비상장법인(사업보고서 제출대상 & IFRS 적용)이
    제출한 정기보고서 내에 XBRL재무제표의 모든계정과목을 제공합니다.

    Args:
        api_key: API 인증키. 발급받은 인증키(40자리). 필수 파라미터입니다.
        corp_code: 고유번호. 공시대상회사의 고유번호(8자리. 예: 00126380). 필수 파라미터입니다.
        bsns_year: 사업연도. 사업연도(4자리). 2015년 이후부터 정보제공됩니다. 필수 파라미터입니다.
        reprt_code: 보고서 코드. 선택 파라미터입니다. 다음 중 하나를 선택할 수 있습니다:
                    - "11013": 1분기보고서
                    - "11012": 반기보고서
                    - "11014": 3분기보고서
                    - "11011": 사업보고서 (기본값)
        fs_div: 개별/연결구분. 선택 파라미터입니다. 다음 중 하나를 선택할 수 있습니다:
                - "OFS": 재무제표 (별도/개별)
                - "CFS": 연결재무제표 (기본값)
        sj_div: 재무제표구분 필터. 선택적 파라미터입니다. 지정하면 해당 재무제표구분의 데이터만 반환됩니다.
                다음 중 하나를 선택할 수 있습니다:
                - "BS": 재무상태표
                - "CIS": 포괄손익계산서
                - "CF": 현금흐름표
                - "SCE": 자본변동표
                None인 경우 모든 재무제표구분의 데이터를 반환합니다 (기본값).

    Returns:
        dict: 재무정보를 담은 딕셔너리. 다음 구조를 가집니다:
            - status (str): 에러 및 정보 코드
            - message (str): 에러 및 정보 메시지
            - list (list): 재무정보 배열. sj_div가 지정된 경우 해당 재무제표구분의 데이터만 포함됩니다.
                          각 항목은 다음 필드를 포함:
                - rcept_no (str): 접수번호(14자리). 접수번호(rcept_no)를 이용하여 공시뷰어에 접근할 수 있습니다.
                - reprt_code (str): 보고서 코드
                - bsns_year (str): 사업 연도
                - corp_code (str): 고유번호 (공시대상회사의 고유번호 8자리)
                - sj_div (str): 재무제표구분 (BS:재무상태표, IS:손익계산서, CIS:포괄손익계산서, CF:현금흐름표, SCE:자본변동표)
                - sj_nm (str): 재무제표명 (예: 재무상태표 또는 손익계산서)
                - account_id (str): 계정ID (XBRL 표준계정ID, 표준계정코드 미사용 시 ""-표준계정코드 미사용-"" 표시)
                - account_nm (str): 계정명 (예: 자본총계)
                - account_detail (str): 계정상세 (자본변동표에만 출력, 예: 자본 [member]|지배기업 소유주지분)
                - thstrm_nm (str): 당기명 (예: 제 13 기)
                - thstrm_amount (str): 당기금액 (분/반기 보고서이면서 (포괄)손익계산서일 경우 [3개월] 금액)
                - thstrm_add_amount (str): 당기누적금액
                - frmtrm_nm (str): 전기명 (예: 제 12 기말)
                - frmtrm_amount (str): 전기금액
                - frmtrm_q_nm (str): 전기명(분/반기) (예: 제 18 기 반기)
                - frmtrm_q_amount (str): 전기금액(분/반기) (분/반기 보고서이면서 (포괄)손익계산서일 경우 [3개월] 금액)
                - frmtrm_add_amount (str): 전기누적금액
                - bfefrmtrm_nm (str): 전전기명 (사업보고서의 경우에만 출력)
                - bfefrmtrm_amount (str): 전전기금액 (사업보고서의 경우에만 출력)
                - ord (str): 계정과목 정렬순서
                - currency (str): 통화 단위
    """
    # 파라미터 검증
    if not api_key or len(api_key) != 40:
        raise ValueError("api_key는 40자리 인증키여야 합니다.")

    if not corp_code or len(corp_code) != 8:
        raise ValueError("corp_code는 8자리 고유번호여야 합니다.")

    # 사업연도 검증
    bsns_year_str = str(bsns_year)
    if len(bsns_year_str) != 4:
        raise ValueError("bsns_year는 4자리여야 합니다.")

    try:
        bsns_year_int = int(bsns_year_str)
        if bsns_year_int < 2015:
            raise ValueError("전자공시의 재무데이터는 2015년 이후 데이터를 제공합니다.")
    except ValueError:
        raise ValueError("bsns_year는 숫자여야 합니다.")

    # 보고서 코드 검증
    valid_reprt_codes = ["11011", "11012", "11013", "11014"]
    if reprt_code not in valid_reprt_codes:
        raise ValueError(f"reprt_code는 다음 중 하나여야 합니다: {', '.join(valid_reprt_codes)}")

    # 개별/연결구분 검증
    valid_fs_divs = ["OFS", "CFS"]
    if fs_div not in valid_fs_divs:
        raise ValueError(f"fs_div는 다음 중 하나여야 합니다: {', '.join(valid_fs_divs)}")

    # 재무제표구분 필터 검증
    if sj_div is not None:
        valid_sj_divs = ["BS", "CIS", "CF", "SCE"]
        if sj_div not in valid_sj_divs:
            raise ValueError(f"sj_div는 다음 중 하나여야 합니다: {', '.join(valid_sj_divs)}")

    url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": bsns_year_str,
        "reprt_code": reprt_code,
        "fs_div": fs_div,
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
            }

            if status != "000":
                error_message = error_codes.get(status, message)
                raise APIError(status, error_message)

        # sj_div 필터링 적용
        if sj_div is not None and "list" in data and isinstance(data["list"], list):
            data["list"] = [item for item in data["list"] if item.get("sj_div") == sj_div]

        return data

    except requests.exceptions.RequestException as e:
        raise APIError("CONNECTION_ERROR", f"API 호출 중 네트워크 오류가 발생했습니다: {str(e)}")
    except Exception as e:
        if isinstance(e, (ValueError, APIError)):
            raise
        raise APIError("UNKNOWN_ERROR", f"예상치 못한 오류가 발생했습니다: {str(e)}")


def xbrlTaxonomy(api_key: str, sj_div: str = "BS1") -> Dict[str, Any]:
    """XBRL 표준계정과목체계(계정과목)를 조회합니다.

    금융감독원 회계포탈에서 제공하는 IFRS 기반 XBRL 재무제표 공시용 표준계정과목체계(계정과목)을 제공합니다.

    Args:
        api_key: API 인증키. 발급받은 인증키(40자리). 필수 파라미터입니다.
        sj_div: 재무제표구분. 선택 파라미터입니다. 다음 중 하나를 선택할 수 있습니다:
                재무상태표:
                  - "BS1": 재무상태표 (연결, 유동/비유동법)
                  - "BS2": 재무상태표 (개별, 유동/비유동법)
                  - "BS3": 재무상태표 (연결, 유동성배열법)
                  - "BS4": 재무상태표 (개별, 유동성배열법)
                별개의 손익계산서:
                  - "IS1": 별개의 손익계산서 (연결, 기능별분류)
                  - "IS2": 별개의 손익계산서 (개별, 기능별분류)
                  - "IS3": 별개의 손익계산서 (연결, 성격별분류)
                  - "IS4": 별개의 손익계산서 (개별, 성격별분류)
                포괄손익계산서:
                  - "CIS1": 포괄손익계산서 (연결, 세후)
                  - "CIS2": 포괄손익계산서 (개별, 세후)
                  - "CIS3": 포괄손익계산서 (연결, 세전)
                  - "CIS4": 포괄손익계산서 (개별, 세전)
                단일 포괄손익계산서:
                  - "DCIS1": 단일 포괄손익계산서 (연결, 기능별분류, 세후포괄손익)
                  - "DCIS2": 단일 포괄손익계산서 (개별, 기능별분류, 세후포괄손익)
                  - "DCIS3": 단일 포괄손익계산서 (연결, 기능별분류, 세전)
                  - "DCIS4": 단일 포괄손익계산서 (개별, 기능별분류, 세전)
                  - "DCIS5": 단일 포괄손익계산서 (연결, 성격별분류, 세후포괄손익)
                  - "DCIS6": 단일 포괄손익계산서 (개별, 성격별분류, 세후포괄손익)
                  - "DCIS7": 단일 포괄손익계산서 (연결, 성격별분류, 세전)
                  - "DCIS8": 단일 포괄손익계산서 (개별, 성격별분류, 세전)
                현금흐름표:
                  - "CF1": 현금흐름표 (연결, 직접법)
                  - "CF2": 현금흐름표 (개별, 직접법)
                  - "CF3": 현금흐름표 (연결, 간접법)
                  - "CF4": 현금흐름표 (개별, 간접법)
                자본변동표:
                  - "SCE1": 자본변동표 (연결)
                  - "SCE2": 자본변동표 (개별)
                기본값: "BS1"

    Returns:
        dict: XBRL 표준계정과목체계 정보를 담은 딕셔너리. 다음 구조를 가집니다:
            - status (str): 에러 및 정보 코드
            - message (str): 에러 및 정보 메시지
            - list (list): 계정과목 정보 배열. 각 항목은 다음 필드를 포함:
                - sj_div (str): 재무제표구분
                - account_id (str): 계정ID (계정 고유명칭)
                - account_nm (str): 계정명
                - bsns_de (str): 기준일 (적용 기준일)
                - label_kor (str): 한글 출력명
                - label_eng (str): 영문 출력명
                - data_tp (str): 데이터 유형. 다음 중 하나:
                    - "text block": 제목
                    - "Text": Text
                    - "yyyy-mm-dd": Date
                    - "X": Monetary Value
                    - "(X)": Monetary Value(Negative)
                    - "X.XX": Decimalized Value
                    - "Shares": Number of shares (주식 수)
                    - "For each": 공시된 항목이 전후로 반복적으로 공시될 경우 사용
                    - 공란: 입력 필요 없음
                - ifrs_ref (str): IFRS Reference (예: K-IFRS 1001 문단 54 (9),K-IFRS 1007 문단 45)
    """
    # 파라미터 검증
    if not api_key or len(api_key) != 40:
        raise ValueError("api_key는 40자리 인증키여야 합니다.")

    # 재무제표구분 검증
    valid_sj_divs = [
        "BS1",
        "BS2",
        "BS3",
        "BS4",
        "IS1",
        "IS2",
        "IS3",
        "IS4",
        "CIS1",
        "CIS2",
        "CIS3",
        "CIS4",
        "DCIS1",
        "DCIS2",
        "DCIS3",
        "DCIS4",
        "DCIS5",
        "DCIS6",
        "DCIS7",
        "DCIS8",
        "CF1",
        "CF2",
        "CF3",
        "CF4",
        "SCE1",
        "SCE2",
    ]
    if sj_div not in valid_sj_divs:
        raise ValueError(f"sj_div는 다음 중 하나여야 합니다: {', '.join(valid_sj_divs)}")

    url = "https://opendart.fss.or.kr/api/xbrlTaxonomy.json"
    params = {
        "crtfc_key": api_key,
        "sj_div": sj_div,
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
