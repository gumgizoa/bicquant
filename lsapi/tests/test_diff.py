import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from crawl_docs import compare_crawls

OLD = Path(__file__).parent / "fixtures" / "crawl_old"
NEW = Path(__file__).parent / "fixtures" / "crawl_new"


@pytest.fixture(scope="module")
def diff():
    return compare_crawls(OLD, NEW)


@pytest.fixture(scope="module")
def changes_by_type(diff):
    result = {}
    for c in diff["changes"]:
        result.setdefault(c["type"], []).append(c)
    return result


def test_category_added(diff):
    assert "신규카테고리" in diff["summary"]["categories_added"]


def test_category_removed(diff):
    assert "기존카테고리" in diff["summary"]["categories_removed"]


def test_api_added(diff):
    assert "주식/[주식] 신규API" in diff["summary"]["apis_added"]


def test_api_removed(diff):
    assert "주식/[주식] 삭제예정" in diff["summary"]["apis_removed"]


def test_basic_changed(changes_by_type):
    api_changes = [c for c in changes_by_type.get("api_changed", []) if c["category"] == "주식" and c["api"] == "[주식] 시세"]
    assert api_changes, "주식/[주식] 시세 api_changed entry not found"
    basic_changes = [ch for ch in api_changes[0]["changes"] if ch["type"] == "basic_changed"]
    desc_change = next((ch for ch in basic_changes if ch["field"] == "description"), None)
    assert desc_change is not None
    assert desc_change["old"] == "주식 현재가 조회"
    assert desc_change["new"] == "주식 현재가 및 호가 조회 (업데이트)"


def test_tr_added(changes_by_type):
    api_changes = [c for c in changes_by_type.get("api_changed", []) if c["category"] == "주식" and c["api"] == "[주식] 시세"]
    assert api_changes
    tr_added = [ch for ch in api_changes[0]["changes"] if ch["type"] == "tr_added"]
    assert any(ch["code"] == "t1102" for ch in tr_added)


def test_tr_removed(changes_by_type):
    api_changes = [c for c in changes_by_type.get("api_changed", []) if c["category"] == "주식" and c["api"] == "[주식] 시세"]
    assert api_changes
    tr_removed = [ch for ch in api_changes[0]["changes"] if ch["type"] == "tr_removed"]
    assert any(ch["code"] == "t1103" for ch in tr_removed)


def _get_t1101_changes(changes_by_type):
    api_changes = [c for c in changes_by_type.get("api_changed", []) if c["category"] == "주식" and c["api"] == "[주식] 시세"]
    assert api_changes
    tr_changes = [ch for ch in api_changes[0]["changes"] if ch["type"] == "tr_changed" and ch["code"] == "t1101"]
    assert tr_changes, "t1101 tr_changed entry not found"
    return tr_changes[0]["changes"]


def test_field_added(changes_by_type):
    t1101_changes = _get_t1101_changes(changes_by_type)
    added = [
        ch for ch in t1101_changes if ch["type"] == "field_added" and ch["section"] == "request_body" and ch["propertyCd"] == "&nbsp;&nbsp;-gubun"
    ]
    assert added


def test_field_removed(changes_by_type):
    t1101_changes = _get_t1101_changes(changes_by_type)
    removed = [
        ch
        for ch in t1101_changes
        if ch["type"] == "field_removed" and ch["section"] == "response_body" and ch["propertyCd"] == "&nbsp;&nbsp;-pricejisu"
    ]
    assert removed


def test_field_changed(changes_by_type):
    t1101_changes = _get_t1101_changes(changes_by_type)
    changed = [
        ch for ch in t1101_changes if ch["type"] == "field_changed" and ch["section"] == "request_header" and ch["propertyCd"] == "authorization"
    ]
    assert changed
    assert "description" in changed[0]["changes"]
    assert changed[0]["changes"]["description"]["old"] == "Bearer token"
    assert changed[0]["changes"]["description"]["new"] == "Bearer {access_token}"


def test_example_changed(changes_by_type):
    t1101_changes = _get_t1101_changes(changes_by_type)
    example_changes = [ch for ch in t1101_changes if ch["type"] == "example_changed" and ch["key"] == "example_request"]
    assert example_changes
    assert "005930" in example_changes[0]["old"]
    assert "gubun" in example_changes[0]["new"]


def test_no_change_in_업종(diff):
    changed_categories = {c["category"] for c in diff["changes"] if c["type"] == "api_changed"}
    removed_categories = {c["category"] for c in diff["changes"] if c["type"] == "category_removed"}
    assert "업종" not in changed_categories
    assert "업종" not in removed_categories
