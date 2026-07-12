"""금융투자협회 FreeSIS(종합통계) 동기 클라이언트.

FreeSIS는 인증이 없다. 모든 통계가 ``/meta/getMetaDataList.do`` 하나로 서빙되고,
``OBJ_NM``이 어떤 통계인지를 고른다. 응답은 ``ds1``에 익명 컬럼(``TMPV1..n``) 행 리스트다.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import requests

from kofiaapi.exceptions import KofiaApiError
from kofiaapi.models import CreditBalance

log = logging.getLogger("kofiaapi")

BASE_URL = "https://freesis.kofia.or.kr"
DATA_PATH = "/meta/getMetaDataList.do"

CREDIT_BALANCE_OBJ = "STATSCU0100000070BO"
"""신용공여 잔고 추이."""

_PERIODS = ("D", "M", "Q", "Y")

# FreeSIS는 브라우저 XHR만 상정하고 만들어져 있어 Referer/XHR 헤더가 없으면 응답이 달라질 수 있다.
# 세션 쿠키(JSESSIONID)는 요구하지 않는다.
_HEADERS = {
    "Content-Type": "application/json; charset=UTF-8",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/stat/FreeSIS.do",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}


def _fmt_date(value: str | date | datetime, param: str) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    if isinstance(value, str):
        try:
            datetime.strptime(value, "%Y%m%d")
        except ValueError as e:
            raise ValueError(f"{param}는 YYYYMMDD 형식이어야 합니다: {value!r} ({e})")
        return value
    raise ValueError(f"{param}는 YYYYMMDD 문자열 또는 date/datetime이어야 합니다: {value!r}")


def build_payload(
    obj_nm: str,
    start: str,
    end: str,
    period: str,
    unit: int,
) -> dict:
    """FreeSIS ``dmSearch`` 요청 바디를 만든다.

    tmpV40은 금액을 나눌 단위다. 1이면 원 단위 원값, 1000000이면 백만원 단위로 반올림되어 내려온다.
    """
    return {
        "dmSearch": {
            "tmpV40": str(unit),
            "tmpV41": "1",
            "tmpV1": period,
            "tmpV45": start,
            "tmpV46": end,
            "OBJ_NM": obj_nm,
        }
    }


class KofiaClient:
    """FreeSIS 통계 조회 클라이언트.

    Usage::

        client = KofiaClient()
        rows = client.credit_balance("20260601", "20260709")   # 신용공여 잔고 추이 (원 단위)
        raw = client.fetch("STATSCU0100000140BO", "20260601", "20260709")  # 임의 통계 원본 행
    """

    def __init__(self, *, session: requests.Session | None = None, timeout: float = 15.0) -> None:
        self._session = session or requests.Session()
        self._timeout = timeout

    def fetch(
        self,
        obj_nm: str,
        start: str | date | datetime,
        end: str | date | datetime,
        *,
        period: str = "D",
        unit: int = 1,
    ) -> list[dict]:
        """통계 원본 행(``ds1``)을 최신 일자부터 내림차순으로 반환한다.

        Args:
            obj_nm: 통계 식별자 (예: ``STATSCU0100000070BO``). 서비스 페이지의 ``serviceId`` + ``BO``.
            start: 조회 시작일.
            end: 조회 종료일.
            period: 자료주기 — ``D``(일) / ``M``(월) / ``Q``(분기) / ``Y``(연).
            unit: 금액 단위. 1이면 원 단위 원값.
        """
        if period not in _PERIODS:
            raise ValueError(f"period는 {_PERIODS} 중 하나여야 합니다: {period!r}")
        if unit < 1:
            raise ValueError(f"unit은 1 이상이어야 합니다: {unit!r}")

        start_s = _fmt_date(start, "start")
        end_s = _fmt_date(end, "end")
        if start_s > end_s:
            raise ValueError(f"start({start_s})는 end({end_s})보다 작거나 같아야 합니다.")

        payload = build_payload(obj_nm, start_s, end_s, period, unit)

        try:
            response = self._session.post(BASE_URL + DATA_PATH, headers=_HEADERS, json=payload, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise KofiaApiError("CONNECTION_ERROR", f"FreeSIS 호출 중 네트워크 오류: {e}")
        except ValueError as e:
            raise KofiaApiError("INVALID_RESPONSE", f"FreeSIS 응답이 JSON이 아닙니다: {e}")

        rows = data.get("ds1")
        if rows is None:
            raise KofiaApiError("INVALID_RESPONSE", f"FreeSIS 응답에 ds1이 없습니다 (obj_nm={obj_nm}): keys={list(data)}")

        log.debug("fetch obj_nm=%s %s~%s period=%s -> %d rows", obj_nm, start_s, end_s, period, len(rows))
        return rows

    def credit_balance(
        self,
        start: str | date | datetime,
        end: str | date | datetime,
        *,
        period: str = "D",
        unit: int = 1,
    ) -> list[CreditBalance]:
        """신용공여 잔고 추이를 조회한다 (신용거래융자/대주, 청약자금대출, 예탁증권담보융자).

        휴장일은 응답에 포함되지 않는다. 반환 순서는 최신 일자부터 내림차순.
        """
        rows = self.fetch(CREDIT_BALANCE_OBJ, start, end, period=period, unit=unit)
        return [CreditBalance.from_row(row) for row in rows]
