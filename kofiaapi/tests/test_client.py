from datetime import date

import pytest

from kofiaapi import CREDIT_BALANCE_OBJ, CreditBalance, KofiaClient, build_payload

# 2026-07-09 실제 응답 행 (원 단위)
SAMPLE_ROW = {
    "TMPV1": "20260709",
    "TMPV2": 36633640504452,
    "TMPV3": 28837404979561,
    "TMPV4": 7796235524891,
    "TMPV5": 27897150881,
    "TMPV6": 23808057269,
    "TMPV7": 4089093612,
    "TMPV8": 0,
    "TMPV9": 25223393125547,
}


def test_build_payload_shape() -> None:
    payload = build_payload(CREDIT_BALANCE_OBJ, "20260601", "20260709", "D", 1)

    assert payload == {
        "dmSearch": {
            "tmpV40": "1",
            "tmpV41": "1",
            "tmpV1": "D",
            "tmpV45": "20260601",
            "tmpV46": "20260709",
            "OBJ_NM": "STATSCU0100000070BO",
        }
    }


def test_credit_balance_row_maps_tmpv_columns() -> None:
    row = CreditBalance.from_row(SAMPLE_ROW)

    assert row.date == date(2026, 7, 9)
    assert row.margin_loan == 36633640504452
    assert row.margin_loan_kospi + row.margin_loan_kosdaq == row.margin_loan
    assert row.stock_loan_kospi + row.stock_loan_kosdaq == row.stock_loan
    assert row.subscription_loan == 0
    assert row.collateral_loan == 25223393125547


def test_fetch_rejects_bad_arguments() -> None:
    client = KofiaClient()

    with pytest.raises(ValueError, match="period"):
        client.fetch(CREDIT_BALANCE_OBJ, "20260601", "20260709", period="W")
    with pytest.raises(ValueError, match="unit"):
        client.fetch(CREDIT_BALANCE_OBJ, "20260601", "20260709", unit=0)
    with pytest.raises(ValueError, match="YYYYMMDD"):
        client.fetch(CREDIT_BALANCE_OBJ, "2026-06-01", "20260709")
    with pytest.raises(ValueError, match="작거나 같아야"):
        client.fetch(CREDIT_BALANCE_OBJ, "20260709", "20260601")


@pytest.mark.slow
def test_live_credit_balance() -> None:
    client = KofiaClient()
    rows = client.credit_balance(date(2026, 6, 1), date(2026, 7, 9))

    assert rows, "조회 구간에 영업일 데이터가 있어야 합니다"
    assert rows[0].date > rows[-1].date, "최신 일자부터 내림차순"
    for row in rows:
        assert row.margin_loan == row.margin_loan_kospi + row.margin_loan_kosdaq
        assert row.margin_loan > 0
        assert row.collateral_loan > 0


@pytest.mark.slow
def test_live_unit_scales_amounts() -> None:
    client = KofiaClient()
    won = client.credit_balance("20260708", "20260709")
    millions = client.credit_balance("20260708", "20260709", unit=1_000_000)

    assert [r.date for r in won] == [r.date for r in millions]
    # 백만 단위 응답은 원 단위 값을 백만으로 반올림한 것
    assert millions[0].margin_loan == round(won[0].margin_loan / 1_000_000)
