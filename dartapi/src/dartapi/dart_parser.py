"""
DART XML → LLM-readable plain text converter.

Converts DART OpenAPI XML documents into clean markdown-structured text
suitable for LLM consumption.

Supported document types (17 validated):
  정기공시   사업보고서 / 반기보고서 / 분기보고서
  지분공시   주식등의대량보유상황보고서 / 임원·주요주주특정증권등소유상황보고서
  기타공시   합병등종료보고서 등
  기업집단   대규모기업집단현황공시
  주요사항   자기주식처분 / 전환사채발행결정 등
  주총공고   주주총회소집공고 (일반 + 정정)
  발행공시   증권신고서 (지분·채무증권) / 투자설명서 / 증권발행실적보고서
  공개매수   공개매수신고서
  감사       감사보고서
  자산유동화 자산유동화관련중요사항발생등보고서

XML quirks handled:
  - lxml recover=True required (some docs contain malformed XML)
  - Korean-named tags e.g. <당기>, <전기> — tail carries real text
  - <삭제/> legal deletion marker → "(삭제)"
  - LIBRARY / TABLE-GROUP: transparent containers
  - SECTION-N nesting same number (기업집단현황): depth-based headings
  - TITLE with block children (공개매수 요약정보): section-container role
  - TABLE: ROWSPAN fill-down, COLSPAN expansion, multi-row header joining
  - Cell types: TH (header), TD (normal), TU (unit), TE (data)
  - IMAGE → "[이미지: caption]" placeholder
  - CORRECTION / PART: treated as section containers
"""

import re
from typing import Optional

from lxml import etree

# ── Constants ──────────────────────────────────────────────────────────────────

CELL_TAGS = {"TH", "TD", "TU", "TE"}

# Layout/binary tags: silently dropped
SKIP_TAGS = {"IMG", "IMG-CAPTION", "PGBRK", "COLGROUP", "COL"}

# Block-level tags that can appear as children of TITLE or SECTION.
# Used to detect "TITLE as section container" vs "TITLE as plain heading".
BLOCK_TAGS = {
    "LIBRARY",
    "TABLE",
    "TABLE-GROUP",
    "P",
    "SECTION-1",
    "SECTION-2",
    "SECTION-3",
    "SECTION-4",
    "SECTION-5",
    "PART",
    "PGBRK",
    "IMAGE",
}


# ── Text helpers ───────────────────────────────────────────────────────────────


def is_korean_tag(tag: str) -> bool:
    """True if tag name contains Korean characters (malformed XML content leak)."""
    return any("\uac00" <= c <= "\ud7a3" for c in str(tag))


def clean(text: str) -> str:
    """Collapse internal whitespace and strip."""
    return re.sub(r"\s+", " ", text).strip()


def get_full_text(elem, joiner: str = " ") -> str:
    """
    Recursively extract all readable text from an element.

    Special cases:
    - Korean malformed tags: reconstruct "tagname + tail" as text
      e.g. <당기/> tail='현황>' → '당기현황'
    - P children: collected as separate items (caller uses joiner="\\n" for cells)
    - SKIP_TAGS: silently dropped
    """
    parts = []

    if elem.text:
        parts.append(elem.text.strip())

    for child in elem:
        if child.tag in SKIP_TAGS:
            pass
        elif is_korean_tag(child.tag):
            # Reconstruct text from tag name + tail, stripping stray '>'
            tail = (child.tail or "").strip()
            parts.append(clean(child.tag + tail.replace(">", "")) if tail else child.tag)
            continue  # tail already consumed
        else:
            child_text = get_full_text(child)
            if child_text:
                parts.append(child_text)

        if not is_korean_tag(child.tag):
            if child.tail and child.tail.strip():
                parts.append(child.tail.strip())

    return joiner.join(filter(None, parts))


def extract_inline_title(title_elem) -> str:
    """
    Extract heading text from a TITLE element, handling two roles:

    (A) Plain TITLE — no block children: return full recursive text.
    (B) Container TITLE — has BLOCK_TAGS children (e.g. 공개매수 요약정보
        where <TITLE ENG="Summary of Information"> wraps a TABLE):
        return only direct inline text; prefer Korean tag names as label
        (e.g. <요약정보/> → "요약정보") and fall back to ENG attribute.
    """
    if not any(c.tag in BLOCK_TAGS for c in title_elem):
        return clean(get_full_text(title_elem))

    # Container TITLE: collect only inline (non-block) text
    inline = clean(title_elem.text or "")
    for c in title_elem:
        if c.tag not in BLOCK_TAGS and not is_korean_tag(c.tag):
            inline = clean(inline + " " + get_full_text(c))

    if not inline:
        korean_label = next((c.tag for c in title_elem if is_korean_tag(c.tag)), None)
        inline = korean_label or title_elem.get("ENG", "")

    return inline


# ── Table parser ───────────────────────────────────────────────────────────────


def parse_table_to_markdown(table_elem) -> Optional[str]:
    """
    Convert TABLE element to a markdown table string.

    Handles:
    - THEAD + TBODY or TBODY-only with mixed TH/TD rows
    - ROWSPAN: fill-down repeats spanned values into subsequent rows
    - COLSPAN: first slot gets text, remaining slots get ""
    - Multi-row headers: columns joined with "/" (deduplicated)
    - Jagged rows normalised to max column count
    """

    def collect_rows(parent, treat_th_as_header: bool):
        rows = []
        for tr in parent.findall("TR"):
            is_header = treat_th_as_header and any(c.tag == "TH" for c in tr)
            cells = []
            for c in tr:
                if c.tag not in CELL_TAGS:
                    continue
                joiner = "\n" if c.find("P") is not None else " "
                txt = get_full_text(c, joiner=joiner) if joiner == "\n" else clean(get_full_text(c))
                rs = int(c.get("ROWSPAN", 1) or 1)
                cs = int(c.get("COLSPAN", 1) or 1)
                cells.append((txt, rs))
                for _ in range(cs - 1):
                    cells.append(("", rs))
            if cells:
                rows.append((is_header, cells))
        return rows

    thead = table_elem.find("THEAD")
    tbody = table_elem.find("TBODY")

    raw_rows = []
    if thead is not None:
        raw_rows = [(True, cells) for _, cells in collect_rows(thead, False)]
    if tbody is not None:
        raw_rows.extend(collect_rows(tbody, treat_th_as_header=True))
    elif thead is None:
        # Flat table with no THEAD/TBODY wrapper
        for tr in table_elem.findall(".//TR"):
            cells = [(clean(get_full_text(c)), int(c.get("ROWSPAN", 1) or 1)) for c in tr if c.tag in CELL_TAGS]
            if cells:
                raw_rows.append((False, cells))

    if not raw_rows:
        return None

    # ROWSPAN fill-down: pending[col] = [text, remaining_rows]
    pending: dict[int, list] = {}
    resolved = []

    max_col = max(len(cells) for _, cells in raw_rows) if raw_rows else 0

    for is_header, cells in raw_rows:
        result_cells = []
        new_idx = 0
        col = 0
        while col < max_col or new_idx < len(cells):
            if col in pending and pending[col][1] > 0:
                result_cells.append(pending[col][0])
                pending[col][1] -= 1
                if pending[col][1] == 0:
                    del pending[col]
                col += 1
            elif new_idx < len(cells):
                txt, rs = cells[new_idx]
                result_cells.append(txt)
                if rs > 1:
                    pending[col] = [txt, rs - 1]
                new_idx += 1
                col += 1
            else:
                break
        resolved.append((is_header, result_cells))

    header_rows = [cells for is_h, cells in resolved if is_h]
    body_rows = [cells for is_h, cells in resolved if not is_h]
    all_rows = header_rows + body_rows
    if not all_rows:
        return None

    # Normalise column count
    max_cols = max(len(r) for r in all_rows)

    def pad(r):
        return r + [""] * (max_cols - len(r))

    header_rows = [pad(r) for r in header_rows]
    body_rows = [pad(r) for r in body_rows]
    all_rows = [pad(r) for r in all_rows]

    def make_row(cells):
        return "| " + " | ".join(cells) + " |"

    separator = "| " + " | ".join(["---"] * max_cols) + " |"
    lines = []

    if header_rows:
        if len(header_rows) == 1:
            lines.append(make_row(header_rows[0]))
        else:
            # Merge multi-row headers: unique values per column joined with "/"
            combined = []
            for col in range(max_cols):
                parts = []
                for hr in header_rows:
                    v = hr[col] if col < len(hr) else ""
                    if v and v not in parts:
                        parts.append(v)
                combined.append("/".join(parts))
            lines.append(make_row(combined))
        lines.append(separator)
        lines.extend(make_row(r) for r in body_rows)
    else:
        lines.append(make_row(all_rows[0]))
        lines.append(separator)
        lines.extend(make_row(r) for r in all_rows[1:])

    return "\n".join(lines)


# ── Block parser ───────────────────────────────────────────────────────────────


def _emit_section(elem, depth: int, title_text: str) -> list[str]:
    """
    Shared rendering for PART / SECTION-N / CORRECTION.
    Emits a heading (if title_text) then recurses into children.
    TITLE children are skipped as headings but their block content is preserved.
    """
    lines = []
    current_depth = depth

    if title_text:
        hashes = "#" * (current_depth + 2)
        lines.append(f"\n{hashes} {title_text}\n")
    else:
        # Shell section with no title: don't consume a heading level
        current_depth = max(0, current_depth - 1)

    for child in elem:
        if child.tag == "TITLE":
            # Heading already emitted above.
            # If TITLE wraps block content (e.g. 요약정보 TABLE), recurse into it.
            for gc in child:
                if gc.tag in BLOCK_TAGS:
                    lines.extend(parse_block(gc, current_depth + 1))
            continue
        lines.extend(parse_block(child, current_depth + 1))

    return lines


def parse_block(elem, depth: int) -> list[str]:
    """
    Recursively parse one XML element into a list of text lines.

    depth: tree depth under BODY (0 = top-level).
           Heading level: depth 0 → ##, 1 → ###, 2 → ####, ...
           Depth is tree-based, not SECTION-tag-number-based, so nested
           SECTION-1 inside SECTION-1 (기업집단현황) renders correctly.
    """
    tag = elem.tag

    # ── Silent drops ──────────────────────────────────────────────────────────
    if tag in SKIP_TAGS or is_korean_tag(tag):
        return []

    # ── IMAGE placeholder ─────────────────────────────────────────────────────
    if tag == "IMAGE":
        captions = [clean(c.text or "") for c in elem.iter("IMG-CAPTION") if (c.text or "").strip()]
        imgs = [clean(c.text or "") for c in elem.iter("IMG") if (c.text or "").strip()]
        label = captions[0] if captions else (imgs[0] if imgs else "")
        return [f"[이미지: {label}]" if label else "[이미지]"]

    # ── Legal deletion marker ─────────────────────────────────────────────────
    if tag == "삭제":
        return ["(삭제)"]

    # ── Section containers ────────────────────────────────────────────────────
    if tag == "PART" or tag.startswith("SECTION-"):
        title_elem = elem.find("TITLE")
        title_text = extract_inline_title(title_elem) if title_elem is not None else ""
        return _emit_section(elem, depth, title_text)

    if tag == "CORRECTION":
        title_elem = elem.find("TITLE")
        title_text = clean(get_full_text(title_elem)) if title_elem is not None else "정정신고"
        return _emit_section(elem, depth, title_text)

    # ── Transparent containers ─────────────────────────────────────────────────
    if tag == "LIBRARY":
        lines = []
        for child in elem:
            lines.extend(parse_block(child, depth))
        return lines

    if tag == "TABLE-GROUP":
        # May contain a TITLE sub-heading; pass depth+1 so it renders one level deeper
        lines = []
        for child in elem:
            lines.extend(parse_block(child, depth + 1))
        return lines

    if tag in ("TBODY", "THEAD", "TR"):
        lines = []
        for child in elem:
            lines.extend(parse_block(child, depth))
        return lines

    # ── Table ─────────────────────────────────────────────────────────────────
    if tag == "TABLE":
        md = parse_table_to_markdown(elem)
        return ["", md, ""] if md else []

    # ── TITLE ─────────────────────────────────────────────────────────────────
    if tag == "TITLE":
        # Two roles:
        # (A) Plain heading — emit as markdown heading only.
        # (B) Container (has BLOCK_TAGS children) — emit heading + recurse into blocks.
        lines = []
        title_text = extract_inline_title(elem)
        if title_text:
            hashes = "#" * (depth + 2)
            lines.append(f"\n{hashes} {title_text}\n")
        for c in elem:
            if c.tag in BLOCK_TAGS:
                lines.extend(parse_block(c, depth + 1))
        return lines

    # ── Cross-reference note ───────────────────────────────────────────────────
    if tag == "A":
        text = clean(get_full_text(elem))
        return [f"  ※ {text}"] if text else []

    # ── Paragraph ─────────────────────────────────────────────────────────────
    if tag == "P":
        spans = list(elem.findall("SPAN"))
        p_text = clean(elem.text or "")
        non_empty_spans = [s for s in spans if clean(get_full_text(s))]

        if not spans:
            # Plain paragraph
            text = clean(get_full_text(elem))
            return [text] if text else []

        if len(non_empty_spans) >= 2 and not p_text:
            # Multiple SPANs, no leading text: itemised list pattern
            return [st for s in non_empty_spans if (st := clean(get_full_text(s)))]

        if len(non_empty_spans) == 1 and p_text:
            # One SPAN after paragraph text
            span_tail = clean(spans[0].tail or "")
            if not span_tail:
                # SPAN is a standalone sub-heading (no tail)
                span_text = clean(get_full_text(spans[0]))
                return [p_text, f"\n**{span_text}**\n"]
            else:
                text = clean(get_full_text(elem))
                return [text] if text else []

        # All other SPAN combinations: flatten to full text
        text = clean(get_full_text(elem))
        return [text] if text else []

    # ── Unknown tag fallback ───────────────────────────────────────────────────
    text = clean(get_full_text(elem))
    return [text] if text else []


# ── Cover page ─────────────────────────────────────────────────────────────────


def parse_cover(cover_elem) -> str:
    """Parse COVER: emit '# [표지]', bold cover title, then all child blocks."""
    lines = ["# [표지]"]

    title_elem = cover_elem.find("COVER-TITLE")
    if title_elem is not None:
        title_text = clean(get_full_text(title_elem))
        if title_text:
            lines.append(f"**{title_text}**")

    for child in cover_elem:
        if child.tag != "COVER-TITLE":
            lines.extend(parse_block(child, depth=0))

    return "\n".join(lines)


# ── Metadata ───────────────────────────────────────────────────────────────────


def parse_meta(root) -> str:
    """
    Extract document-level metadata into a header block.
    TU unit field names vary by doc type:
      정기공시  → PERIODFROM / PERIODTO
      지분공시  → RPT_RSP_DT / RPT_REF_DT
      기타공시  → RPT_RSN_TP
    """
    meta = {}

    for tag in ("DOCUMENT-NAME", "COMPANY-NAME", "FORMULA-VERSION"):
        elem = root.find(tag)
        if elem is not None and elem.text:
            meta[tag] = elem.text.strip()

    TU_FIELD_MAP = {
        "PERIODFROM": "period_from",
        "PERIODTO": "period_to",
        "RPT_RSP_DT": "report_obligation_date",
        "RPT_REF_DT": "report_base_date",
        "RPT_RSN_TP": "report_type_detail",
    }
    for tu in root.iter("TU"):
        unit = tu.get("AUNIT", "")
        if unit in TU_FIELD_MAP:
            meta[TU_FIELD_MAP[unit]] = (tu.text or "").strip() or tu.get("AUNITVALUE", "")

    lines = [
        "=" * 60,
        f"문서 유형  : {meta.get('DOCUMENT-NAME', 'N/A')}",
        f"회사명     : {meta.get('COMPANY-NAME', 'N/A')}",
    ]
    if "period_from" in meta or "period_to" in meta:
        lines.append(f"사업연도   : {meta.get('period_from', '')} ~ {meta.get('period_to', '')}")
    if "report_obligation_date" in meta:
        lines.append(f"보고의무발생일   : {meta['report_obligation_date']}")
    if "report_base_date" in meta:
        lines.append(f"보고서작성기준일 : {meta['report_base_date']}")
    if "report_type_detail" in meta:
        lines.append(f"보고유형         : {meta['report_type_detail']}")
    lines.append("=" * 60)

    return "\n".join(lines)


# ── Entry point ────────────────────────────────────────────────────────────────


def parse_dart_to_text(xml_input: str | bytes, include_meta: bool = True) -> str:
    """
    Parse a DART XML document into clean, LLM-readable plain text.

    Args:
        xml_input: Raw XML as str or bytes. Accepts malformed XML (lxml recover mode).
        include_meta: Whether to include metadata in the output.

    Returns:
        Structured plain text with markdown headings and tables.
    """
    if isinstance(xml_input, str):
        xml_input = xml_input.encode("utf-8")

    parser = etree.XMLParser(recover=True, encoding="utf-8")
    root = etree.fromstring(xml_input, parser=parser)

    parts = []
    if include_meta:
        parts.append(parse_meta(root))

    cover = root.find(".//COVER")
    if cover is not None:
        parts.append(parse_cover(cover))

    body_elem = root.find(".//BODY")
    body = body_elem if body_elem is not None else root
    for child in body:
        if child.tag == "COVER":
            continue
        blocks = parse_block(child, depth=0)
        if blocks:
            parts.append("\n".join(blocks))

    return "\n\n".join(parts)


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        raise ValueError("Usage: python dart_parser.py <filepath>")

    with open(filepath, "rb") as f:
        raw = f.read()

    result = parse_dart_to_text(raw)

    out_path = filepath.replace(".xml", "_parsed.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"✅  {out_path}")
    print(f"    input {len(raw):,} bytes  →  output {len(result):,} chars")
    print(f"\n--- preview ---\n{result[:2000]}")
