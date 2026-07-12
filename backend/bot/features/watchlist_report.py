"""관심종목 일일 리포트 메시지 포맷 — bot 전용 feature.

순수 함수만 담는다. LS 데이터 페치와 텔레그램 발송은 ``bot.main``에 있다.

entry 스키마 (모든 지표 필드는 없을 수 있음):
    code, name, is_kr
    ratio      : 이격도 (float | None)
    mdd        : 최대낙폭 % (float | None), mdd_days: 실제 사용 거래일 수
    credit     : t1926 dict  | None  (융자/대주 잔고)
    short      : t1927 최신행 dict | None  (공매도)
    lending    : t1941 최신행 dict | None  (대차)
"""

from __future__ import annotations


def _num(v, default: float = 0.0) -> float:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return default


def _stock_lines(e: dict, dev_threshold: float, mdd_alert: float) -> list[str]:
    flag = "🇰🇷" if e.get("is_kr") else "🇺🇸"
    lines = [f"<b>{e['name']} ({e['code']})</b> {flag}"]

    ratio = e.get("ratio")
    if ratio is not None:
        mark = "⚠️ " if ratio >= dev_threshold else ""
        lines.append(f"📊 이격도 {mark}{ratio:.1f}")

    mdd = e.get("mdd")
    if mdd is not None:
        mark = "⚠️ " if mdd <= mdd_alert else ""
        lines.append(f"📉 MDD {mark}{mdd:.1f}% (최근 {e.get('mdd_days', 0)} 거래일)")

    c = e.get("credit")
    if c:
        lines.append(f"💳 융자 잔고 {int(_num(c.get('yjvolume'))):,}주 / {int(_num(c.get('yjprice'))):,}백만원")
        lines.append(f"    잔고율 {_num(c.get('yjrate')):.2f}% · 공여율 {_num(c.get('ygrate')):.2f}%")
        lines.append(f"    5일 {_num(c.get('yj5days')):+.2f}% · 20일 {_num(c.get('yj20days')):+.2f}%")
        lines.append(f"    대주잔고 {int(_num(c.get('djvolume'))):,}주")

    s = e.get("short")
    if s:
        lines.append(f"📉 공매도 {int(_num(s.get('gm_vo'))):,}주 / {int(_num(s.get('gm_va'))):,}백만원")
        lines.append(f"    비중 {_num(s.get('gm_per')):.2f}% · 누적 {int(_num(s.get('gm_vo_sum'))):,}주")

    ln = e.get("lending")
    if ln:
        lines.append(f"🔁 대차 신규 {int(_num(ln.get('upvolume'))):,} / 상환 {int(_num(ln.get('dnvolume'))):,}")
        lines.append(f"    잔고 {int(_num(ln.get('tovolume'))):,}주 · 증감 {int(_num(ln.get('tovoldif'))):+,}")

    return lines


def format_watchlist_report(
    entries: list[dict],
    *,
    dev_threshold: float,
    mdd_alert: float,
    label: str | None = None,
) -> str:
    """관심종목 리포트를 HTML 텔레그램 메시지로 렌더링.

    ``label``이 있으면 헤더에 태그로 붙는다 (예: '장 마감'). 수동 조회처럼 맥락이
    필요 없으면 생략한다.
    """
    header = f"📋 <b>관심종목 리포트 ({label})</b>" if label else "📋 <b>관심종목 리포트</b>"
    if not entries:
        return f"{header}\n\n관심종목이 없어요. /watch {{코드}} 로 추가해보세요."

    blocks = [header]
    for e in entries:
        blocks.append("\n".join(_stock_lines(e, dev_threshold, mdd_alert)))
    return "\n\n".join(blocks)
