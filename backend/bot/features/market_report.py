"""시장 요약 리포트 메시지 포맷 (지수 이격도 + ADR) — bot 전용 feature.

순수 함수만 담는다. LS 데이터 페치와 텔레그램 발송은 ``bot.main``에 있다.
관심종목 리포트는 ``bot/features/watchlist_report.py``의 별도 메시지로 나간다.

``label``이 있으면 헤더에 태그로 붙는다 (예: '장 마감'). 수동 조회(/market)처럼
맥락이 필요 없으면 생략한다.
"""

from __future__ import annotations


def adr_from_rows(rows: list[dict], period: int) -> float | None:
    """t1514(업종기간별추이) 행에서 ADR(등락비율)을 계산한다.

    ADR = 100 * sum(상승 종목수) / sum(하락 종목수), 최근 ``period`` 일봉 기준.
    행의 ``high``/``low``가 각각 상승/하락 종목수다. 데이터가 없거나 하락 종목수 합이
    0이면 ``None`` (0으로 나누기 회피).
    """
    rows = sorted(rows, key=lambda r: r.get("date", ""))[-period:]
    up_sum = sum(int(float(r["high"])) for r in rows if str(r.get("high", "")).strip())
    down_sum = sum(int(float(r["low"])) for r in rows if str(r.get("low", "")).strip())
    if down_sum == 0:
        return None
    return 100.0 * up_sum / down_sum


def deviation_ratio(closes: list[float]) -> float | None:
    """이격도 = 최근 종가 / MA50 * 100. 종가가 51개 미만이거나 MA50이 0이면 ``None``.

    MA50은 최근 종가를 뺀 직전 50개 봉의 평균이다 (``closes[-51:-1]``).
    """
    if len(closes) < 51:
        return None
    ma50 = sum(closes[-51:-1]) / 50
    if ma50 <= 0:
        return None
    return closes[-1] / ma50 * 100


def _header(title: str, label: str | None) -> str:
    return f"<b>{title} ({label})</b>" if label else f"<b>{title}</b>"


def format_deviation_summary(entries: list[dict], threshold: float, label: str | None = None) -> str:
    """지수 이격도 요약.

    Args:
        entries: code, name, current, ma50, ratio 키를 가진 dict 리스트.
        threshold: 이 값 이상이면 강조.
        label: 헤더 태그 (예: '장 시작', '장 마감').
    """
    lines = [f"📊 {_header('이격도 일일 요약', label)}", ""]
    for e in entries:
        ratio = e["ratio"]
        if ratio >= threshold:
            lines.append(f"⚠️ {e['name']} ({e['code']}): <b>{ratio:.1f}</b>")
        else:
            lines.append(f"• {e['name']} ({e['code']}): {ratio:.1f}")
    return "\n".join(lines)


def format_adr_summary(entries: list[dict], overbought: float, oversold: float, label: str | None = None) -> str:
    """ADR(등락비율) 요약.

    Args:
        entries: code, name, adr 키를 가진 dict 리스트.
        overbought: 이 값 이상이면 과열.
        oversold: 이 값 이하면 바닥.
        label: 헤더 태그.
    """
    lines = [f"📈 {_header('ADR 일일 요약', label)}", ""]
    for e in entries:
        adr = e["adr"]
        if adr >= overbought:
            lines.append(f"⚠️ {e['name']} ({e['code']}): <b>{adr:.1f}</b> (과열)")
        elif adr <= oversold:
            lines.append(f"🔻 {e['name']} ({e['code']}): <b>{adr:.1f}</b> (바닥)")
        else:
            lines.append(f"• {e['name']} ({e['code']}): {adr:.1f}")
    return "\n".join(lines)


def format_market_report(
    index_entries: list[dict],
    adr_entries: list[dict],
    *,
    dev_threshold: float,
    adr_overbought: float,
    adr_oversold: float,
    label: str | None = None,
) -> str | None:
    """시장 요약(이격도 + ADR)을 하나의 텔레그램 메시지로 렌더링.

    양쪽 다 데이터가 없으면 ``None``을 반환한다 (보낼 게 없다).
    """
    parts = []
    if index_entries:
        parts.append(format_deviation_summary(index_entries, dev_threshold, label=label))
    if adr_entries:
        parts.append(format_adr_summary(adr_entries, adr_overbought, adr_oversold, label=label))
    return "\n\n".join(parts) if parts else None
