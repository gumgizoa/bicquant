"""Build index.json, blocks.json, catalog.json from crawled data.

Usage:
    python scripts/build_specs.py                  # latest crawl
    python scripts/build_specs.py 20260526_000345  # specific crawl
"""

import argparse
import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
SPECS_DIR = Path(__file__).parent.parent / "src" / "lsapi" / "specs"

# propertyType code → human-readable type name
_TYPE_MAP = {
    "A0001": "String",
    "A0004": "Int",
    "A0003": "Object",
    "A0005": "Array",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_name(prop_cd: str) -> str:
    """'&nbsp;&nbsp;-shcode' → 'shcode'"""
    return prop_cd.replace("&nbsp;", " ").strip().lstrip("- ").strip()


def _clean_desc(raw) -> str:
    if not raw:
        return ""
    return re.sub(r"<[^>]+>", " ", raw).strip()


def _is_block_type(prop_type: str) -> bool:
    return prop_type in ("A0003", "A0005")


# ---------------------------------------------------------------------------
# Block parser
# ---------------------------------------------------------------------------


def _parse_blocks(rows: list[dict]) -> dict:
    """Parse request_body / response_body rows into structured blocks.

    Result:
        {
            "t1101InBlock": {
                "type": "Object",
                "fields": [
                    {"name": "shcode", "label": "short code", "type": "String",
                     "length": "6", "required": True, "description": ""}
                ]
            }
        }
    """
    blocks: dict = {}
    prefix_to_block: dict[str, str] = {}  # order prefix → block name

    for row in rows:
        order = (row.get("propertyOrder") or "").strip()
        prop_cd = (row.get("propertyCd") or "").strip()
        prop_type = row.get("propertyType", "")
        prop_nm = (row.get("propertyNm") or "").strip()
        parts = order.split(".") if order else []

        if len(parts) == 1:
            # Top-level row → block header (A0003 Object or A0005 Array)
            block_name = prop_cd
            blocks[block_name] = {
                "type": "Array" if prop_type == "A0005" else "Object",
                "fields": [],
            }
            prefix_to_block[parts[0]] = block_name

        elif len(parts) >= 2:
            prefix = parts[0]

            # Ensure parent block exists (some TRs omit the block-header row)
            if prefix not in prefix_to_block:
                fallback = f"Block{prefix}"
                blocks[fallback] = {"type": "Object", "fields": []}
                prefix_to_block[prefix] = fallback

            block_name = prefix_to_block[prefix]
            clean_cd = _strip_name(prop_cd)
            if not clean_cd:
                continue

            # Sub-block: block type AND null length AND name looks like a block
            is_subblock = _is_block_type(prop_type) and row.get("propertyLength") is None and re.search(r"[Bb]lock\d*$", clean_cd)

            if is_subblock:
                blocks[block_name]["fields"].append(
                    {
                        "name": clean_cd,
                        "label": prop_nm,
                        "type": "Array" if prop_type == "A0005" else "Object",
                        "length": None,
                        "required": row.get("requireYn") == "Y",
                        "description": "",
                    }
                )
            else:
                # Regular scalar field
                # A0003 used as a field (malformed spec) → treat as Int
                ftype = "Int" if prop_type == "A0003" else _TYPE_MAP.get(prop_type, prop_type)
                blocks[block_name]["fields"].append(
                    {
                        "name": clean_cd,
                        "label": prop_nm,
                        "type": ftype,
                        "length": row.get("propertyLength"),
                        "required": row.get("requireYn") == "Y",
                        "description": _clean_desc(row.get("description")),
                    }
                )

    return blocks


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build(crawl_dir: Path, specs_dir: Path) -> None:
    specs_dir.mkdir(parents=True, exist_ok=True)

    index: dict = {}  # tr_code → metadata
    blocks: dict = {}  # tr_code → {in_blocks, out_blocks}
    catalog: list = []  # [{group info with tr list}]

    for f in sorted(crawl_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))

        for api in data.get("apis", []):
            group_name = api["name"]
            category = api["category"]
            basic = api["basic"]
            tr_codes: list[str] = []

            for tr in api.get("trs", []):
                code = tr.get("code", "")
                if not code:
                    continue
                tr_codes.append(code)

                index[code] = {
                    "name": tr.get("name", ""),
                    "group": group_name,
                    "category": category,
                    "method": basic.get("method", ""),
                    "url": basic.get("url", ""),
                    "domain": basic.get("domain_prod", ""),
                    "content_type": basic.get("content_type", ""),
                    "tps_limit": tr.get("tps_limit"),
                }

                blocks[code] = {
                    "in_blocks": _parse_blocks(tr.get("request_body", [])),
                    "out_blocks": _parse_blocks(tr.get("response_body", [])),
                }

            catalog.append(
                {
                    "name": group_name,
                    "category": category,
                    "method": basic.get("method", ""),
                    "url": basic.get("url", ""),
                    "domain": basic.get("domain_prod", ""),
                    "trs": tr_codes,
                }
            )

    (specs_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    (specs_dir / "blocks.json").write_text(json.dumps(blocks, ensure_ascii=False, indent=2), encoding="utf-8")
    (specs_dir / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    tr_count = len(index)
    group_count = len(catalog)
    print(f"index.json  : {tr_count} TRs")
    print(f"blocks.json : {tr_count} TRs")
    print(f"catalog.json: {group_count} groups")
    print(f"저장 → {specs_dir}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _latest_crawl_dir() -> Path:
    dirs = sorted(p for p in DATA_DIR.iterdir() if p.is_dir() and re.match(r"\d{8}_\d{6}$", p.name))
    if not dirs:
        sys.exit("크롤링 데이터 없음 — crawl_docs.py를 먼저 실행하세요")
    return dirs[-1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("crawl_ts", nargs="?", help="크롤링 타임스탬프 (예: 20260526_000345)")
    args = parser.parse_args()

    crawl_dir = DATA_DIR / args.crawl_ts if args.crawl_ts else _latest_crawl_dir()
    if not crawl_dir.exists():
        sys.exit(f"크롤링 디렉토리 없음: {crawl_dir}")

    print(f"크롤링 데이터: {crawl_dir.name}")
    build(crawl_dir, SPECS_DIR)
