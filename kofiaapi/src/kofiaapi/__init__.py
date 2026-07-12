"""금융투자협회 FreeSIS (freesis.kofia.or.kr) 클라이언트.

인증 없이 통계를 조회한다::

    from kofiaapi import KofiaClient

    client = KofiaClient()
    rows = client.credit_balance("20260601", "20260709")   # 신용공여 잔고 추이
    rows[0].margin_loan                                    # 신용거래융자 전체 (원)

    client.fetch("STATSCU0100000140BO", "20260601", "20260709")  # 임의 통계 원본 행
"""

from kofiaapi.client import CREDIT_BALANCE_OBJ, KofiaClient, build_payload
from kofiaapi.exceptions import KofiaApiError
from kofiaapi.models import CreditBalance

__all__ = [
    "KofiaClient",
    "CreditBalance",
    "KofiaApiError",
    "CREDIT_BALANCE_OBJ",
    "build_payload",
]

__version__ = "0.1.0"
