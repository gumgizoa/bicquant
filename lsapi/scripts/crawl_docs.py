"""Crawl LS Securities OpenAPI documentation and save specs as JSON.

Usage:
    python scripts/crawl_docs.py              # crawl + diff vs previous
    python scripts/crawl_docs.py --diff-only  # diff last two crawls, no network
"""

import argparse
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

from playwright.async_api import Page, async_playwright

BASE_URL = "https://openapi.ls-sec.co.kr/apiservice"
DATA_DIR = Path(__file__).parent.parent / "data"

# Fields compared when detecting changes in a property row
_PROP_KEYS = ("propertyCd", "propertyNm", "propertyType", "propertyLength", "requireYn", "description")
_BASIC_KEYS = ("method", "url", "domain_prod", "domain_mock", "format", "content_type", "description")


# ---------------------------------------------------------------------------
# Playwright helpers
# ---------------------------------------------------------------------------


async def dismiss_modals(page: Page) -> None:
    await page.evaluate("""
        () => {
            document.querySelectorAll('.modal.show').forEach(m => {
                m.classList.remove('show');
                m.style.display = 'none';
            });
            document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
            document.body.classList.remove('modal-open');
        }
    """)


async def get_nav_items(page: Page) -> list[dict]:
    await page.goto(BASE_URL, wait_until="networkidle", timeout=30_000)
    await dismiss_modals(page)

    items = await page.evaluate("""
        () => {
            const results = [];
            const re = /goLeftMenuUrl\\("([0-9a-f-]{36})",\\s*"([0-9a-f-]{36})"/;
            const uuidRe = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

            document.querySelectorAll('nav#lnb > ul > li').forEach(catLi => {
                if (!uuidRe.test(catLi.id)) return;
                const catAnchor = catLi.querySelector('ul.second-depth > li > a:not([onclick])');
                const category = catAnchor ? catAnchor.textContent.trim() : '';
                catLi.querySelectorAll('ul.third-depth li a[onclick]').forEach(a => {
                    const m = (a.getAttribute('onclick') || '').match(re);
                    if (m) results.push({ name: a.textContent.trim(), group_id: m[1], api_id: m[2], category });
                });
            });
            return results;
        }
    """)

    seen: set[str] = set()
    unique = []
    for item in items:
        if item["api_id"] not in seen:
            seen.add(item["api_id"])
            unique.append(item)
    return unique


async def scrape_api_page(page: Page, item: dict, retries: int = 3) -> dict:
    api_id = item["api_id"]
    page_url = f"{BASE_URL}?group_id={item['group_id']}&api_id={api_id}"

    for attempt in range(1, retries + 1):
        try:
            await page.goto(page_url, wait_until="networkidle", timeout=30_000)
            await dismiss_modals(page)
            break
        except Exception:
            if attempt == retries:
                raise
            await asyncio.sleep(3 * attempt)

    api_info = await page.evaluate("async (id) => (await fetch('/api/apis/public/' + id)).json()", api_id)
    tr_list = await page.evaluate("async (id) => (await fetch('/api/apis/guide/tr/' + id)).json()", api_id)

    tps_map: dict[str, int | None] = await page.evaluate("""
        () => {
            const result = {};
            document.querySelectorAll('.cardApi').forEach(card => {
                const code = card.querySelector('.apiCode')?.textContent.trim();
                const tps  = card.querySelector('.apiTest')?.textContent.trim();
                if (code) { const v = parseInt(tps, 10); result[code] = isNaN(v) ? null : v; }
            });
            return result;
        }
    """)

    trs = []
    for tr in tr_list:
        props = await page.evaluate(
            "async (id) => (await fetch('/api/apis/guide/tr/property/' + id)).json()",
            tr["id"],
        )
        code = tr.get("trCode", "")
        trs.append(
            {
                "name": tr.get("trName", ""),
                "code": code,
                "tps_limit": tps_map.get(code),
                "request_header": [p for p in props if p.get("bodyType") == "req_h"],
                "request_body": [p for p in props if p.get("bodyType") == "req_b"],
                "response_header": [p for p in props if p.get("bodyType") == "res_h"],
                "response_body": [p for p in props if p.get("bodyType") == "res_b"],
                "example_request": tr.get("reqExample", ""),
                "example_response": tr.get("resExample", ""),
            }
        )

    return {
        "name": item["name"],
        "category": item["category"],
        "basic": {
            "method": api_info.get("httpMethod", ""),
            "url": api_info.get("accessUrl", ""),
            "domain_prod": api_info.get("domain", ""),
            "domain_mock": api_info.get("simulatedDomain", ""),
            "format": api_info.get("reqFormat", ""),
            "content_type": api_info.get("contentType", ""),
            "description": api_info.get("description", ""),
        },
        "trs": trs,
    }


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _crawl_dirs() -> list[Path]:
    """Return all crawl dirs sorted oldest-first."""
    dirs = sorted(p for p in DATA_DIR.iterdir() if p.is_dir() and re.match(r"\d{8}_\d{6}$", p.name))
    return dirs


def _save_crawl(results: dict[str, list[dict]], ts: str) -> Path:
    crawl_dir = DATA_DIR / ts
    crawl_dir.mkdir(parents=True, exist_ok=True)
    for cat, apis in results.items():
        safe = re.sub(r'[/\\:*?"<>|]', "_", cat)
        (crawl_dir / f"{safe}.json").write_text(
            json.dumps({"category": cat, "scraped_at": ts, "apis": apis}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return crawl_dir


def _load_crawl(crawl_dir: Path) -> dict[str, dict]:
    """Load a crawl dir as {category: {name: api_spec}}."""
    result: dict[str, dict] = {}
    for f in crawl_dir.glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        cat = data.get("category", f.stem)
        result[cat] = {api["name"]: api for api in data.get("apis", [])}
    return result


# ---------------------------------------------------------------------------
# Diff logic
# ---------------------------------------------------------------------------


def _norm_props(fields: list[dict]) -> dict[str, dict]:
    """Index property rows by propertyCd, keeping only comparison keys."""
    out: dict[str, dict] = {}
    for f in fields:
        cd = f.get("propertyCd", "").strip()
        if cd:
            out[cd] = {k: f.get(k, "") for k in _PROP_KEYS}
    return out


def _diff_fields(old: list[dict], new: list[dict]) -> list[dict]:
    old_m, new_m = _norm_props(old), _norm_props(new)
    changes = []
    for cd in sorted(set(new_m) - set(old_m)):
        changes.append({"type": "field_added", "propertyCd": cd, "new": new_m[cd]})
    for cd in sorted(set(old_m) - set(new_m)):
        changes.append({"type": "field_removed", "propertyCd": cd, "old": old_m[cd]})
    for cd in sorted(set(old_m) & set(new_m)):
        if old_m[cd] != new_m[cd]:
            diff = {k: {"old": old_m[cd].get(k), "new": new_m[cd].get(k)} for k in _PROP_KEYS if old_m[cd].get(k) != new_m[cd].get(k)}
            if diff:
                changes.append({"type": "field_changed", "propertyCd": cd, "changes": diff})
    return changes


def _diff_tr(old_tr: dict, new_tr: dict) -> list[dict]:
    changes = []
    if old_tr.get("tps_limit") != new_tr.get("tps_limit"):
        changes.append({"type": "tps_changed", "old": old_tr.get("tps_limit"), "new": new_tr.get("tps_limit")})
    for section in ("request_header", "request_body", "response_header", "response_body"):
        fc = _diff_fields(old_tr.get(section, []), new_tr.get(section, []))
        for c in fc:
            c["section"] = section
            changes.append(c)
    for key in ("example_request", "example_response"):
        if old_tr.get(key) != new_tr.get(key):
            changes.append({"type": "example_changed", "key": key, "old": old_tr.get(key, ""), "new": new_tr.get(key, "")})
    return changes


def _diff_api(old_api: dict, new_api: dict) -> list[dict]:
    changes = []

    # basic info
    for k in _BASIC_KEYS:
        ov, nv = old_api.get("basic", {}).get(k), new_api.get("basic", {}).get(k)
        if ov != nv:
            changes.append({"type": "basic_changed", "field": k, "old": ov, "new": nv})

    # TRs indexed by code
    old_trs = {tr["code"]: tr for tr in old_api.get("trs", []) if tr.get("code")}
    new_trs = {tr["code"]: tr for tr in new_api.get("trs", []) if tr.get("code")}

    for code in sorted(set(new_trs) - set(old_trs)):
        changes.append({"type": "tr_added", "code": code, "name": new_trs[code].get("name", "")})
    for code in sorted(set(old_trs) - set(new_trs)):
        changes.append({"type": "tr_removed", "code": code, "name": old_trs[code].get("name", "")})
    for code in sorted(set(old_trs) & set(new_trs)):
        tr_changes = _diff_tr(old_trs[code], new_trs[code])
        if tr_changes:
            changes.append({"type": "tr_changed", "code": code, "name": new_trs[code].get("name", ""), "changes": tr_changes})
    return changes


def compare_crawls(old_dir: Path, new_dir: Path) -> dict:
    old = _load_crawl(old_dir)
    new = _load_crawl(new_dir)

    old_cats, new_cats = set(old), set(new)
    changes = []

    for cat in sorted(new_cats - old_cats):
        changes.append({"type": "category_added", "category": cat, "apis": list(new[cat].keys())})
    for cat in sorted(old_cats - new_cats):
        changes.append({"type": "category_removed", "category": cat, "apis": list(old[cat].keys())})

    for cat in sorted(old_cats & new_cats):
        old_apis, new_apis = old[cat], new[cat]
        for name in sorted(set(new_apis) - set(old_apis)):
            changes.append({"type": "api_added", "category": cat, "api": name})
        for name in sorted(set(old_apis) - set(new_apis)):
            changes.append({"type": "api_removed", "category": cat, "api": name})
        for name in sorted(set(old_apis) & set(new_apis)):
            api_changes = _diff_api(old_apis[name], new_apis[name])
            if api_changes:
                changes.append({"type": "api_changed", "category": cat, "api": name, "changes": api_changes})

    return {
        "new_crawl": new_dir.name,
        "prev_crawl": old_dir.name,
        "summary": {
            "categories_added": [c["category"] for c in changes if c["type"] == "category_added"],
            "categories_removed": [c["category"] for c in changes if c["type"] == "category_removed"],
            "apis_added": [f"{c['category']}/{c['api']}" for c in changes if c["type"] == "api_added"],
            "apis_removed": [f"{c['category']}/{c['api']}" for c in changes if c["type"] == "api_removed"],
            "apis_changed": len([c for c in changes if c["type"] == "api_changed"]),
            "total_changes": len(changes),
        },
        "changes": changes,
    }


def _print_diff_summary(diff: dict) -> None:
    s = diff["summary"]
    print(f"\n=== 변경 내역: {diff['prev_crawl']} → {diff['new_crawl']} ===")
    if s["total_changes"] == 0:
        print("  변경 없음")
        return

    if s["categories_added"]:
        print(f"  카테고리 추가: {s['categories_added']}")
    if s["categories_removed"]:
        print(f"  카테고리 삭제: {s['categories_removed']}")
    if s["apis_added"]:
        print(f"  API 추가: {s['apis_added']}")
    if s["apis_removed"]:
        print(f"  API 삭제: {s['apis_removed']}")
    if s["apis_changed"]:
        print(f"  API 변경: {s['apis_changed']}건")
        for c in diff["changes"]:
            if c["type"] != "api_changed":
                continue
            print(f"    [{c['category']}] {c['api']}")
            for ch in c["changes"]:
                t = ch["type"]
                if t == "basic_changed":
                    print(f"      기본정보 변경: {ch['field']}  {ch['old']!r} → {ch['new']!r}")
                elif t == "tr_added":
                    print(f"      TR 추가: {ch['code']} ({ch['name']})")
                elif t == "tr_removed":
                    print(f"      TR 삭제: {ch['code']} ({ch['name']})")
                elif t == "tr_changed":
                    field_changes = len(ch["changes"])
                    print(f"      TR 변경: {ch['code']} ({ch['name']}) — {field_changes}건")
                    for fc in ch["changes"]:
                        ft = fc["type"]
                        sec = fc.get("section", "")
                        if ft == "field_added":
                            print(f"        [{sec}] 필드 추가: {fc['propertyCd']}")
                        elif ft == "field_removed":
                            print(f"        [{sec}] 필드 삭제: {fc['propertyCd']}")
                        elif ft == "field_changed":
                            for fk, fv in fc["changes"].items():
                                print(f"        [{sec}] {fc['propertyCd']}.{fk}: {fv['old']!r} → {fv['new']!r}")
                        elif ft == "tps_changed":
                            print(f"        TPS 변경: {fc['old']} → {fc['new']}")
                        elif ft == "example_changed":
                            print(f"        예시 변경: {fc['key']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def run_crawl() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("Phase 1: 사이드바 탐색...")
        nav_items = await get_nav_items(page)
        categories = sorted(set(i["category"] for i in nav_items))
        print(f"  {len(nav_items)}개 API / {len(categories)}개 카테고리\n")

        print("Phase 2: API 명세 크롤링...")
        results: dict[str, list[dict]] = {}
        errors: list[dict] = []

        for idx, item in enumerate(nav_items, 1):
            print(f"[{idx}/{len(nav_items)}] {item['category']} / {item['name']}", end="", flush=True)
            try:
                spec = await scrape_api_page(page, item)
                results.setdefault(item["category"], []).append(spec)
                print(" ✓")
            except Exception as exc:
                print(f" ✗ {exc}")
                errors.append({"item": item, "error": str(exc)})

        await browser.close()

    print(f"\nPhase 3: JSON 저장 → data/{ts}/")
    crawl_dir = _save_crawl(results, ts)
    for cat, apis in results.items():
        safe = re.sub(r'[/\\:*?"<>|]', "_", cat)
        print(f"  {safe}.json  ({len(apis)} APIs)")

    if errors:
        err_path = crawl_dir / "_errors.json"
        err_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n에러 {len(errors)}건 → {err_path}")

    total = sum(len(v) for v in results.values())
    print(f"\n총 {total}개 API 저장 완료")
    return crawl_dir


def run_diff(new_dir: Path) -> None:
    dirs = _crawl_dirs()
    prev_dirs = [d for d in dirs if d != new_dir]
    if not prev_dirs:
        print("\n이전 크롤링 없음 — diff 생략")
        return

    prev_dir = prev_dirs[-1]
    diff = compare_crawls(prev_dir, new_dir)

    diff_path = DATA_DIR / f"diff_{new_dir.name}.json"
    diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDiff 저장: {diff_path.name}")

    _print_diff_summary(diff)


async def main(diff_only: bool = False) -> None:
    if diff_only:
        dirs = _crawl_dirs()
        if len(dirs) < 2:
            print("비교할 크롤링 데이터가 2개 이상 필요합니다.")
            return
        run_diff(dirs[-1])
        return

    new_dir = await run_crawl()
    run_diff(new_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--diff-only", action="store_true", help="크롤링 없이 최근 두 결과를 비교만 함")
    args = parser.parse_args()
    asyncio.run(main(diff_only=args.diff_only))
