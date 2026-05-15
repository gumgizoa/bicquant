import asyncio
import json

from playwright.async_api import Page, async_playwright

BASE_URL = "https://openapi.ls-sec.co.kr/apiservice"

TARGET = {
    "name": "[업종] 시세",
    "category": "업종",
    "group_id": "f82999f4-eb1a-4ead-a0b1-a4386e8721ab",
    "api_id": "88a7c0d3-fb4f-48ef-bc9b-4c47ac72a87b",
}


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


async def scrape_api_page(page: Page, item: dict) -> dict:
    api_id = item["api_id"]

    page_url = f"{BASE_URL}?group_id={item['group_id']}&api_id={api_id}"
    await page.goto(page_url, wait_until="networkidle", timeout=30_000)
    await dismiss_modals(page)

    # 페이지 컨텍스트에서 fetch 호출 (세션·쿠키 그대로 사용)
    api_info = await page.evaluate(
        "async (id) => (await fetch('/api/apis/public/' + id)).json()", api_id
    )
    tr_list = await page.evaluate(
        "async (id) => (await fetch('/api/apis/guide/tr/' + id)).json()", api_id
    )

    trs = []
    for tr in tr_list:
        tr_id = tr["id"]
        props = await page.evaluate(
            "async (id) => (await fetch('/api/apis/guide/tr/property/' + id)).json()",
            tr_id,
        )
        trs.append(
            {
                "name": tr.get("trName", ""),
                "code": tr.get("trCode", ""),
                "request_header": [p for p in props if p.get("bodyType") == "req_h"],
                "request_body": [p for p in props if p.get("bodyType") == "req_b"],
                "response_header": [p for p in props if p.get("bodyType") == "res_h"],
                "response_body": [p for p in props if p.get("bodyType") == "res_b"],
                "example_request": tr.get("reqExample", ""),
                "example_response": tr.get("resExample", ""),
            }
        )

    basic = {
        "method": api_info.get("httpMethod", ""),
        "url": api_info.get("accessUrl", ""),
        "domain_prod": api_info.get("domain", ""),
        "domain_mock": api_info.get("simulatedDomain", ""),
        "format": api_info.get("reqFormat", ""),
        "content_type": api_info.get("contentType", ""),
        "description": api_info.get("description", ""),
    }

    return {
        "name": item["name"],
        "category": item["category"],
        "basic": basic,
        "trs": trs,
    }


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        result = await scrape_api_page(page, TARGET)
        print(json.dumps(result, ensure_ascii=False, indent=2))

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
