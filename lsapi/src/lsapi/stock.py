"""High-level convenience wrappers for frequently-used 주식 TRs.

These methods are thin wrappers around :meth:`LSClient.call`; every method
returns the raw :class:`TRResponse` so callers can inspect the full body. The
value is hiding the TR code, input-block name, and common parameter defaults so
application code reads like domain vocabulary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lsapi.client import TRResponse

if TYPE_CHECKING:
    from lsapi.client import LSClient


# Order-price pattern codes (OrdprcPtnCode) as documented by LS OpenAPI.
ORD_PRC_LIMIT = "00"  # 지정가
ORD_PRC_MARKET = "03"  # 시장가
ORD_PRC_COND_LIMIT = "05"  # 조건부지정가
ORD_PRC_BEST_LIMIT = "06"  # 최유리지정가
ORD_PRC_PRIOR_LIMIT = "07"  # 최우선지정가
ORD_PRC_BEFORE_MARKET = "61"  # 장전 시간외 종가
ORD_PRC_AFTER_MARKET = "81"  # 장후 시간외 종가
ORD_PRC_AFTER_SINGLE = "82"  # 시간외 단일가

# Buy/Sell type codes (BnsTpCode)
BNS_SELL = "1"
BNS_BUY = "2"


class StockAPI:
    """Wrappers for [주식] quote / chart / account / order TRs."""

    def __init__(self, client: "LSClient") -> None:
        self._c = client

    # ============================================== 시세 (quotes)

    def quote(self, shcode: str) -> TRResponse:
        """t1101 — 주식 현재가 호가 조회 (10단 호가 + 체결)."""
        return self._c.call("t1101", shcode=shcode)

    def current_price(self, shcode: str) -> TRResponse:
        """t1102 — 주식 현재가(시세) 조회."""
        return self._c.call("t1102", shcode=shcode)

    def tick_history(self, shcode: str) -> TRResponse:
        """t1104 — 주식 현재가 체결 메모 (최근 체결 내역)."""
        return self._c.call("t1104", shcode=shcode)

    def pivot(self, shcode: str) -> TRResponse:
        """t1105 — 주식 피봇/피크 조회."""
        return self._c.call("t1105", shcode=shcode)

    def time_ticks(
        self,
        shcode: str,
        *,
        cvolume: int = 0,
        starttime: str = "",
        endtime: str = "",
        cts_time: str = "",
    ) -> TRResponse:
        """t1301 — 시간대별 체결 조회."""
        return self._c.call(
            "t1301",
            shcode=shcode,
            cvolume=cvolume,
            starttime=starttime,
            endtime=endtime,
            cts_time=cts_time,
        )

    def period_prices(
        self,
        shcode: str,
        *,
        dwmcode: str = "1",  # 1:일 2:주 3:월 4:연
        date: str = "",  # yyyymmdd
        idx: int = 0,
        cnt: int = 500,
    ) -> TRResponse:
        """t1305 — 기간별 주가."""
        return self._c.call("t1305", shcode=shcode, dwmcode=dwmcode, date=date, idx=idx, cnt=cnt)

    def multi_current_price(self, *shcodes: str) -> TRResponse:
        """t8407 — 복수 종목 멀티 현재가 조회.

        ``t8407InBlock`` expects ``nrec`` (count) and a concatenated ``shcode``
        string of 6-character codes without delimiters.
        """
        if not shcodes:
            raise ValueError("at least one shcode required")
        nrec = len(shcodes)
        code_blob = "".join(c.strip() for c in shcodes)
        return self._c.call("t8407", nrec=nrec, shcode=code_blob)

    # ============================================== 차트 (charts)

    def daily_chart(
        self,
        shcode: str,
        *,
        sdate: str = "",
        edate: str = "",
        qrycnt: int = 500,
        gubun: str = "2",  # 1:주 2:일 3:월 4:분
        cts_date: str = "",
        comp_yn: str = "N",  # 수정주가 보정
        sujung: str = "",
    ) -> TRResponse:
        """t8410 — 주식 차트 (일/주/월/연봉)."""
        return self._c.call(
            "t8410",
            shcode=shcode,
            gubun=gubun,
            qrycnt=qrycnt,
            sdate=sdate,
            edate=edate,
            cts_date=cts_date,
            comp_yn=comp_yn,
            sujung=sujung,
        )

    def tick_chart(
        self,
        shcode: str,
        *,
        ncnt: int = 1,  # 틱 단위
        qrycnt: int = 500,
        nday: str = "0",
        sdate: str = "",
        stime: str = "",
        edate: str = "",
        etime: str = "",
        cts_date: str = "",
        cts_time: str = "",
        comp_yn: str = "N",
    ) -> TRResponse:
        """t8411 — 주식 차트 (틱 / n틱)."""
        return self._c.call(
            "t8411",
            shcode=shcode,
            ncnt=ncnt,
            qrycnt=qrycnt,
            nday=nday,
            sdate=sdate,
            stime=stime,
            edate=edate,
            etime=etime,
            cts_date=cts_date,
            cts_time=cts_time,
            comp_yn=comp_yn,
        )

    def minute_chart(
        self,
        shcode: str,
        *,
        ncnt: int = 1,  # n분 단위
        qrycnt: int = 500,
        nday: str = "0",
        sdate: str = "",
        stime: str = "",
        edate: str = "",
        etime: str = "",
        cts_date: str = "",
        cts_time: str = "",
        comp_yn: str = "N",
    ) -> TRResponse:
        """t8412 — 주식 차트 (N분봉)."""
        return self._c.call(
            "t8412",
            shcode=shcode,
            ncnt=ncnt,
            qrycnt=qrycnt,
            nday=nday,
            sdate=sdate,
            stime=stime,
            edate=edate,
            etime=etime,
            cts_date=cts_date,
            cts_time=cts_time,
            comp_yn=comp_yn,
        )

    # ============================================== 계좌 (account)

    def balance(
        self,
        *,
        prcgb: str = "1",  # 1:평균단가 2:BEP단가
        chegb: str = "2",  # 2:체결기준
        dangb: str = "0",  # 0:전체
        charge: str = "1",  # 수수료 포함 여부
        cts_expcode: str = "",
    ) -> TRResponse:
        """t0424 — 주식 잔고2."""
        return self._c.call("t0424", prcgb=prcgb, chegb=chegb, dangb=dangb, charge=charge, cts_expcode=cts_expcode)

    def orders_and_fills(
        self,
        *,
        expcode: str = "",
        chegb: str = "0",  # 0:전체 1:체결 2:미체결
        medosu: str = "0",  # 0:전체 1:매도 2:매수
        sortgb: str = "1",  # 1:역순 2:정순
        cts_ordno: str = "",
    ) -> TRResponse:
        """t0425 — 주식 체결/미체결 조회."""
        return self._c.call("t0425", expcode=expcode, chegb=chegb, medosu=medosu, sortgb=sortgb, cts_ordno=cts_ordno)

    def available_cash(self, *, bal_cre_tp: str = "0") -> TRResponse:
        """CSPAQ12200 — 현물계좌 주문가능금액/수량 상세."""
        return self._c.call("CSPAQ12200", BalCreTp=bal_cre_tp)

    # ============================================== 주문 (orders)

    def order(
        self,
        *,
        shcode: str,
        qty: int,
        price: int = 0,
        side: str = BNS_BUY,
        ord_prc_pattern: str = ORD_PRC_LIMIT,
        mgn_trn_code: str = "000",
        loan_dt: str = "",
        ord_condi: str = "0",
        mbr_no: str = "",
    ) -> TRResponse:
        """CSPAT00601 — 현금 신규 주문 (매수/매도)."""
        return self._c.call(
            "CSPAT00601",
            IsuNo=shcode,
            OrdQty=qty,
            OrdPrc=price,
            BnsTpCode=side,
            OrdprcPtnCode=ord_prc_pattern,
            MgntrnCode=mgn_trn_code,
            LoanDt=loan_dt,
            OrdCndiTpCode=ord_condi,
            MbrNo=mbr_no,
        )

    def buy(self, shcode: str, qty: int, price: int = 0, *, market: bool = False, **extra) -> TRResponse:
        """Convenience: 매수. ``market=True`` uses 시장가 (price forced to 0)."""
        return self.order(
            shcode=shcode,
            qty=qty,
            price=0 if market else price,
            side=BNS_BUY,
            ord_prc_pattern=ORD_PRC_MARKET if market else ORD_PRC_LIMIT,
            **extra,
        )

    def sell(self, shcode: str, qty: int, price: int = 0, *, market: bool = False, **extra) -> TRResponse:
        """Convenience: 매도."""
        return self.order(
            shcode=shcode,
            qty=qty,
            price=0 if market else price,
            side=BNS_SELL,
            ord_prc_pattern=ORD_PRC_MARKET if market else ORD_PRC_LIMIT,
            **extra,
        )

    def modify(
        self,
        *,
        orig_ord_no: int,
        shcode: str,
        qty: int,
        price: int,
        ord_prc_pattern: str = ORD_PRC_LIMIT,
        ord_condi: str = "0",
    ) -> TRResponse:
        """CSPAT00701 — 정정 주문."""
        return self._c.call(
            "CSPAT00701",
            OrgOrdNo=orig_ord_no,
            IsuNo=shcode,
            OrdQty=qty,
            OrdprcPtnCode=ord_prc_pattern,
            OrdCndiTpCode=ord_condi,
            OrdPrc=price,
        )

    def cancel(self, *, orig_ord_no: int, shcode: str, qty: int) -> TRResponse:
        """CSPAT00801 — 취소 주문."""
        return self._c.call("CSPAT00801", OrgOrdNo=orig_ord_no, IsuNo=shcode, OrdQty=qty)

    # ============================================== 종목 검색 (search)

    def master(self, *, gubun: str = "1") -> TRResponse:
        """t8430 — 주식 종목 조회 (gubun 1:코스피, 2:코스닥, 0:전체)."""
        return self._c.call("t8430", gubun=gubun)

    def condition_search(self, *, gubun: str = "0", jm_gb: str = "0", jmcode: str = "", cts: str = "") -> TRResponse:
        """t1809 — 신호 조회 (조건검색 신호 리스트)."""
        return self._c.call("t1809", gubun=gubun, jmGb=jm_gb, jmcode=jmcode, cts=cts)
