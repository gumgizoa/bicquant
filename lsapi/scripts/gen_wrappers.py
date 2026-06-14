"""Generate per-category Python wrappers from the crawled specs.

Each REST API group becomes a module under ``src/lsapi/generated/`` with one
method per TR code, exposed as ``client.api.<slug>.<tr_code>(...)``. Realtime
(WebSocket) groups are not given REST wrappers — instead their TR codes are
listed in ``src/lsapi/realtime_topics.py`` for use with the realtime client.

Run:
    python scripts/gen_wrappers.py

The output is fully regenerated — do not edit generated files by hand.
"""

from __future__ import annotations

import json
import keyword
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "src" / "lsapi" / "specs"
DEST_REST = ROOT / "src" / "lsapi" / "generated"
DEST_RT = ROOT / "src" / "lsapi" / "realtime_topics.py"

PYTHON_KEYWORDS = set(keyword.kwlist) | {"match", "case", "type"}

# Korean REST group name → (module slug, Python class name)
GROUP_SLUGS: dict[str, tuple[str, str]] = {
    "[주식] 시세": ("stock_quote", "StockQuoteAPI"),
    "[주식] 차트": ("stock_chart", "StockChartAPI"),
    "[주식] 계좌": ("stock_account", "StockAccountAPI"),
    "[주식] 주문": ("stock_order", "StockOrderAPI"),
    "[주식] 거래원": ("stock_brokers", "StockBrokersAPI"),
    "[주식] 종목검색": ("stock_search", "StockSearchAPI"),
    "[주식] 투자정보": ("stock_info", "StockInfoAPI"),
    "[주식] 프로그램": ("stock_program", "StockProgramAPI"),
    "[주식] 상위종목": ("stock_top", "StockTopAPI"),
    "[주식] ETF": ("stock_etf", "StockEtfAPI"),
    "[주식] ELW": ("stock_elw", "StockElwAPI"),
    "[주식] 섹터": ("stock_sector", "StockSectorAPI"),
    "[주식] 기타": ("stock_misc", "StockMiscAPI"),
    "[주식] 투자자": ("stock_investor", "StockInvestorAPI"),
    "[주식] 외인/기관": ("stock_foreign", "StockForeignAPI"),
    "[선물/옵션] 시세": ("futures_quote", "FuturesQuoteAPI"),
    "[선물/옵션] 차트": ("futures_chart", "FuturesChartAPI"),
    "[선물/옵션] 계좌": ("futures_account", "FuturesAccountAPI"),
    "[선물/옵션] 주문": ("futures_order", "FuturesOrderAPI"),
    "[선물/옵션] 투자자": ("futures_investor", "FuturesInvestorAPI"),
    "[선물/옵션] 기타": ("futures_misc", "FuturesMiscAPI"),
    "[해외주식] 시세": ("overseas_stock_quote", "OverseasStockQuoteAPI"),
    "[해외주식] 차트": ("overseas_stock_chart", "OverseasStockChartAPI"),
    "[해외주식] 계좌": ("overseas_stock_account", "OverseasStockAccountAPI"),
    "[해외주식] 주문": ("overseas_stock_order", "OverseasStockOrderAPI"),
    "[해외선물] 시세": ("overseas_futures_quote", "OverseasFuturesQuoteAPI"),
    "[해외선물] 차트": ("overseas_futures_chart", "OverseasFuturesChartAPI"),
    "[해외선물] 계좌": ("overseas_futures_account", "OverseasFuturesAccountAPI"),
    "[해외선물] 주문": ("overseas_futures_order", "OverseasFuturesOrderAPI"),
    "[업종] 시세": ("sector_quote", "SectorQuoteAPI"),
    "[업종] 차트": ("sector_chart", "SectorChartAPI"),
    "[기타] 시간조회": ("misc_time", "MiscTimeAPI"),
    "접근토큰 발급": ("auth_token", "AuthTokenAPI"),
    "접근토큰 폐기": ("auth_revoke", "AuthRevokeAPI"),
}

# Realtime (WebSocket) group name → category slug
RT_GROUP_SLUGS: dict[str, str] = {
    "[주식] 실시간 시세": "stock",
    "[선물/옵션] 실시간 시세": "futures",
    "[해외주식] 실시간 시세": "overseas_stock",
    "[해외선물] 실시간 시세": "overseas_futures",
    "[업종] 실시간 시세": "sector",
    "[기타] 실시간 시세": "etc",
    "[실시간 시세 투자정보] 투자정보": "investinfo",
}


def safe_param(name: str) -> str:
    """Transform a raw field name into a legal Python parameter name."""
    n = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not n or not (n[0].isalpha() or n[0] == "_"):
        n = "_" + n
    if n in PYTHON_KEYWORDS:
        n = n + "_"
    return n


def clean_block_name(name: str) -> str:
    """Strip the crawled ``(Occurs)`` array annotation; gateway wants the bare name."""
    return name.replace("(Occurs)", "").strip()


def _primary_block(tr_code: str, in_blocks: dict) -> str | None:
    for bname in in_blocks:
        if clean_block_name(bname).lower().startswith(tr_code.lower()):
            return bname
    return next(iter(in_blocks)) if in_blocks else None


def make_method(tr_code: str, info: dict, blocks: dict) -> str:
    in_blocks = blocks.get("in_blocks") or {}
    out_blocks = blocks.get("out_blocks") or {}
    tr_name = info.get("name") or ""
    rate = info.get("tps_limit")
    rate_str = str(rate) if rate else "-"

    primary = _primary_block(tr_code, in_blocks)
    primary_clean = clean_block_name(primary) if primary else None

    # Keyword-only params (one per field of the primary in-block), default "".
    param_alias: list[tuple[str, str]] = []  # (py_name, raw_field)
    if primary:
        for fld in in_blocks[primary].get("fields", []):
            raw = fld["name"]
            param_alias.append((safe_param(raw), raw))

    has_secondary = len(in_blocks) > 1

    doc = [f'        """{tr_code} — {tr_name}.', ""]
    doc.append(f"        Endpoint : {info.get('method', 'POST')} {info.get('domain', '')}{info.get('url', '')}")
    doc.append(f"        Rate/sec : {rate_str}")
    if primary_clean:
        doc.append(f"        In  block: {primary_clean}")
    if out_blocks:
        doc.append(f"        Out block(s): {', '.join(clean_block_name(b) for b in out_blocks)}")
    if has_secondary:
        doc.append("        Extra input blocks exist — pass them via ``extra_blocks={...}``.")
    doc.append('        """')

    # Signature
    params = ["self"]
    if param_alias or has_secondary:
        params.append("*")
    params.extend(f'{py}: str | int = ""' for py, _ in param_alias)
    if has_secondary:
        params.append("extra_blocks: dict | None = None")
    signature = f"    def {tr_code}({', '.join(params)}) -> TRResponse:"

    # Body construction + dispatch
    if primary_clean:
        pairs = ", ".join(f'"{raw}": {py}' for py, raw in param_alias)
        body_line = f'        body = {{"{primary_clean}": {{{pairs}}}}}'
    else:
        body_line = "        body = {}"
    if has_secondary:
        body_line += "\n        if extra_blocks:\n            body.update(extra_blocks)"
    call_line = f'        return self._c.call("{tr_code}", body)'

    return signature + "\n" + "\n".join(doc) + "\n" + body_line + "\n" + call_line + "\n"


def make_class_file(class_name: str, group_name: str, methods: list[tuple[str, dict, dict]]) -> str:
    header = (
        '"""AUTOGENERATED by scripts/gen_wrappers.py — do not edit by hand.\n\n'
        f"Wrapper for LS OpenAPI group: {group_name}\n"
        '"""\n'
        "from __future__ import annotations\n\n"
        "from typing import TYPE_CHECKING\n\n"
        "from ..client import TRResponse\n\n"
        "if TYPE_CHECKING:\n"
        "    from ..client import LSClient\n\n\n"
    )
    body = [f"class {class_name}:"]
    body.append(f'    """{group_name} — {len(methods)} TR(s)."""')
    body.append("")
    body.append('    def __init__(self, client: "LSClient") -> None:')
    body.append("        self._c = client")
    body.append("")
    for tr_code, info, blocks in sorted(methods, key=lambda x: x[0].lower()):
        body.append(make_method(tr_code, info, blocks))
    return header + "\n".join(body) + "\n"


def make_facade(class_map: dict[str, tuple[str, str]]) -> str:
    out = [
        '"""AUTOGENERATED by scripts/gen_wrappers.py — do not edit by hand.\n\nFacade exposing every LS OpenAPI category as a sub-attribute.\n"""',
        "from __future__ import annotations",
        "",
        "from typing import TYPE_CHECKING",
        "",
    ]
    for slug, (cls, _) in sorted(class_map.items()):
        out.append(f"from .{slug} import {cls}")
    out += ["", "if TYPE_CHECKING:", "    from ..client import LSClient", "", ""]
    out.append("class GeneratedAPI:")
    out.append('    """Bundle every auto-generated category wrapper."""')
    out.append("")
    out.append('    def __init__(self, client: "LSClient") -> None:')
    for slug, (cls, _) in sorted(class_map.items()):
        out.append(f"        self.{slug}: {cls} = {cls}(client)")
    out += ["", "", "__all__ = ["]
    out.append('    "GeneratedAPI",')
    for _, (cls, _name) in sorted(class_map.items()):
        out.append(f'    "{cls}",')
    out.append("]")
    return "\n".join(out) + "\n"


def make_realtime_topics(rt_map: dict[str, list[tuple[str, str]]]) -> str:
    out = [
        '"""AUTOGENERATED by scripts/gen_wrappers.py — do not edit by hand.\n\n'
        "Realtime (WebSocket) TR code lists grouped by category. Use with\n"
        "``LSWebSocketClient.subscribe(tr_cd, tr_key, callback)``.\n"
        '"""',
        "from __future__ import annotations",
        "",
        "# Mapping of category slug → {tr_code: human name}",
        "REALTIME_TOPICS: dict[str, dict[str, str]] = {",
    ]
    for slug, entries in sorted(rt_map.items()):
        out.append(f'    "{slug}": {{')
        for code, name in sorted(entries):
            out.append(f"        {json.dumps(code, ensure_ascii=False)}: {json.dumps(name, ensure_ascii=False)},")
        out.append("    },")
    out.append("}")
    out += ["", "", "def list_topics(category: str | None = None) -> list[str]:"]
    out.append('    """Return realtime TR codes; if ``category`` given, only that slug."""')
    out.append("    if category is None:")
    out.append("        return [c for v in REALTIME_TOPICS.values() for c in v]")
    out.append("    return list(REALTIME_TOPICS.get(category, {}).keys())")
    return "\n".join(out) + "\n"


def main() -> None:
    index = json.loads((SPECS / "index.json").read_text(encoding="utf-8"))
    blocks = json.loads((SPECS / "blocks.json").read_text(encoding="utf-8"))

    rest_groups: dict[str, list[tuple[str, dict, dict]]] = {}
    rt_groups: dict[str, list[tuple[str, str]]] = {}
    missing_slugs: set[str] = set()

    for code, info in index.items():
        code = code.strip()
        group = info.get("group") or ""
        if group in RT_GROUP_SLUGS:
            rt_groups.setdefault(RT_GROUP_SLUGS[group], []).append((code, info.get("name") or ""))
        elif group in GROUP_SLUGS:
            slug, _cls = GROUP_SLUGS[group]
            rest_groups.setdefault(slug, []).append((code, info, blocks.get(code, {})))
        else:
            missing_slugs.add(group)

    if missing_slugs:
        print("WARNING: groups without slug mapping:", missing_slugs, file=sys.stderr)

    DEST_REST.mkdir(parents=True, exist_ok=True)
    for p in DEST_REST.glob("*.py"):
        p.unlink()

    class_map: dict[str, tuple[str, str]] = {}
    for group_name, (slug, class_name) in GROUP_SLUGS.items():
        methods = rest_groups.get(slug, [])
        if not methods:
            continue
        (DEST_REST / f"{slug}.py").write_text(make_class_file(class_name, group_name, methods), encoding="utf-8")
        class_map[slug] = (class_name, group_name)
        print(f"  {slug:28s} {len(methods):3d} TR(s)")

    (DEST_REST / "__init__.py").write_text(make_facade(class_map), encoding="utf-8")
    DEST_RT.write_text(make_realtime_topics(rt_groups), encoding="utf-8")
    print()
    print(f"REST wrappers   : {sum(len(v) for v in rest_groups.values())} TRs across {len(class_map)} groups")
    print(f"Realtime topics : {sum(len(v) for v in rt_groups.values())} TRs across {len(rt_groups)} groups")


if __name__ == "__main__":
    main()
