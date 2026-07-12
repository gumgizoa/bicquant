"""해외 거시 지표 리포트 메시지 포맷 (미 국채 10년물 + 미국 M2) — bot 전용 feature.

순수 함수만 담는다. FRED 데이터 페치와 텔레그램 발송은 ``bot.main``에 있다.
시장 요약(``market_report``)은 국내 지수 중심이라, 해외 거시 지표는 별도 메시지로 나간다.

두 지표는 성격이 다르다:
- 국채 10년물(DGS10)은 일별이라 전 관측치 대비 변동폭(%p)을 보여준다.
- M2(M2SL)는 월별이라 장중은 물론 한 달 내내 같은 값이다. 그래서 값 자체보다
  전월/전년 대비 증가율이 정보량이고, 헤더가 아니라 각 줄에 데이터 기준월을 명시한다.

한국 M2는 아직 없다. FRED의 한국 M2 계열(MYAGM2KRM189S)이 2017년에 끊겨서 쓸 수 없고,
한국은행 ECOS 오픈API 키가 생기면 여기에 한 줄로 붙인다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MacroPoint:
    """거시 시계열의 최신 관측치 하나와, 증감 계산에 필요한 과거 관측치.

    ``date``는 데이터 기준일이다 (조회일이 아니다 — 두 지표 모두 발표가 지연된다).
    """

    date: date
    value: float
    prev: float | None = None
    """직전 관측치. 일별 계열이면 직전 거래일, 월별 계열이면 전월."""
    year_ago: float | None = None
    """12개월 전 관측치. 월별 계열의 YoY 계산에만 쓴다."""


def _pct_change(current: float, past: float | None) -> float | None:
    """전 기간 대비 증감률(%). 과거 값이 없거나 0이면 ``None``."""
    if not past:
        return None
    return (current - past) / past * 100


def _arrow(diff: float) -> str:
    return "▲" if diff > 0 else "▼" if diff < 0 else "━"


def _fmt_pct_change(label: str, current: float, past: float | None) -> str | None:
    """'▲ 1.09% MoM' 형태. 과거 값이 없으면 ``None``."""
    pct = _pct_change(current, past)
    if pct is None:
        return None
    return f"{_arrow(pct)} {abs(pct):.2f}% {label}"


def format_treasury_yield(point: MacroPoint, move_alert: float) -> str:
    """미 국채 10년물 금리. 직전 거래일 대비 변동폭이 ``move_alert``(%p) 이상이면 강조."""
    parts = [f"<b>{point.value:.2f}%</b>"]
    prefix = "🇺🇸"

    if point.prev is not None:
        diff = point.value - point.prev
        parts.append(f"({_arrow(diff)} {abs(diff):.2f}%p, {point.date:%Y-%m-%d} 기준)")
        if abs(diff) >= move_alert:
            prefix = "⚠️"
    else:
        parts.append(f"({point.date:%Y-%m-%d} 기준)")

    return f"{prefix} 미 국채 10년물: {' '.join(parts)}"


def _fmt_usd_bn(value: float) -> str:
    """십억 달러 단위 값을 조 달러로 축약. 23052.3 → '23.05조 달러'."""
    if abs(value) >= 1000:
        return f"{value / 1000:,.2f}조 달러"
    return f"{value:,.1f}십억 달러"


def format_m2(name: str, point: MacroPoint) -> str:
    """M2 통화량. 월별이라 값보다 전월(MoM)/전년(YoY) 대비 증감률이 핵심이다."""
    changes = [c for c in (_fmt_pct_change("MoM", point.value, point.prev), _fmt_pct_change("YoY", point.value, point.year_ago)) if c]
    suffix = f"{' · '.join(changes)}, {point.date:%Y-%m} 기준" if changes else f"{point.date:%Y-%m} 기준"
    return f"🇺🇸 {name} M2: <b>{_fmt_usd_bn(point.value)}</b> ({suffix})"


def format_macro_report(
    treasury: MacroPoint | None,
    m2_us: MacroPoint | None,
    *,
    treasury_move_alert: float,
    label: str | None = None,
) -> str | None:
    """해외 거시 지표를 하나의 텔레그램 메시지로 렌더링.

    ``label``이 있으면 헤더에 태그로 붙는다 (예: '장 마감'). 한 지표를 못 가져와도
    나머지는 나간다. 둘 다 없으면 ``None``을 반환한다 (보낼 게 없다).
    """
    lines: list[str] = []
    if treasury is not None:
        lines.append(format_treasury_yield(treasury, treasury_move_alert))
    if m2_us is not None:
        lines.append(format_m2("미국", m2_us))
    if not lines:
        return None

    header = f"<b>해외 거시 지표 ({label})</b>" if label else "<b>해외 거시 지표</b>"
    return "\n".join([f"🌐 {header}", "", *lines])
