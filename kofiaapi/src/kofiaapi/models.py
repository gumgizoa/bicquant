"""FreeSIS 응답 행(row)을 도메인 모델로 변환한다.

FreeSIS는 모든 통계를 ``TMPV1..TMPVn`` 이라는 익명 컬럼으로 내려주고, 컬럼의 의미는
서비스별 그리드 메타(``getSrvData.do``의 ``dsGrid``)에만 존재한다. 따라서 각 통계마다
TMPV 순번 → 필드 매핑을 여기에 명시적으로 박아둔다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


@dataclass(frozen=True)
class CreditBalance:
    """신용공여 잔고 추이 (STATSCU0100000070) 한 행. 금액 단위는 조회 시 지정한 단위(기본 원)."""

    date: date
    margin_loan: int
    """신용거래융자 전체."""
    margin_loan_kospi: int
    """신용거래융자 유가증권."""
    margin_loan_kosdaq: int
    """신용거래융자 코스닥."""
    stock_loan: int
    """신용거래대주 전체."""
    stock_loan_kospi: int
    """신용거래대주 유가증권."""
    stock_loan_kosdaq: int
    """신용거래대주 코스닥."""
    subscription_loan: int
    """청약자금 대출."""
    collateral_loan: int
    """예탁증권 담보융자."""

    @classmethod
    def from_row(cls, row: dict) -> CreditBalance:
        return cls(
            date=_parse_date(row["TMPV1"]),
            margin_loan=int(row["TMPV2"]),
            margin_loan_kospi=int(row["TMPV3"]),
            margin_loan_kosdaq=int(row["TMPV4"]),
            stock_loan=int(row["TMPV5"]),
            stock_loan_kospi=int(row["TMPV6"]),
            stock_loan_kosdaq=int(row["TMPV7"]),
            subscription_loan=int(row["TMPV8"]),
            collateral_loan=int(row["TMPV9"]),
        )
