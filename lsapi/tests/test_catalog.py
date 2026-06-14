"""Tests for the spec catalog loaded from the detailed blocks.json."""

from lsapi import default_catalog


def test_build_body_kwargs_form() -> None:
    spec = default_catalog().tr("t1101")
    assert spec.build_body(shcode="005930") == {"t1101InBlock": {"shcode": "005930"}}
    assert spec.primary_in_block == "t1101InBlock"


def test_detailed_fields_are_preserved() -> None:
    """The catalog must keep the rich per-field metadata (label/type/required)."""
    spec = default_catalog().tr("t1101")
    block = spec.first_in_block()
    assert block is not None
    field = block.fields[0]
    assert field.name == "shcode"
    assert field.label  # Korean label retained
    assert field.required is True


def test_occurs_annotation_stripped_from_block_name() -> None:
    spec = default_catalog().tr("o3107")
    assert spec.primary_in_block == "o3107InBlock"
    assert all("(Occurs)" not in b.name for b in (*spec.in_blocks, *spec.out_blocks))


def test_realtime_flag() -> None:
    cat = default_catalog()
    assert cat.tr("t1101").is_realtime is False
    assert cat.tr("JIF").is_realtime is True


def test_search_and_group() -> None:
    cat = default_catalog()
    assert any(s.code == "t1101" for s in cat.search("t1101"))
    assert any(s.code == "t1101" for s in cat.find_by_group("시세"))
