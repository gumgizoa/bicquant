"""TR catalog: loads specs and provides lookup by TR code."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lsapi.exceptions import LSSpecError

_SPECS_DIR = Path(__file__).parent / "specs"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str  # Korean display name
    type: str  # "String" | "Int" | "Object" | "Array"
    length: str | None
    required: bool
    description: str


@dataclass(frozen=True)
class BlockSpec:
    name: str
    type: str  # "Object" | "Array"
    fields: tuple[FieldSpec, ...]


@dataclass(frozen=True)
class TRSpec:
    code: str
    name: str
    group: str
    category: str
    method: str
    url: str
    domain: str
    content_type: str
    tps_limit: int | None
    in_blocks: tuple[BlockSpec, ...]
    out_blocks: tuple[BlockSpec, ...]

    @property
    def is_realtime(self) -> bool:
        return self.domain.startswith("wss://")

    def first_in_block(self) -> BlockSpec | None:
        """Return the first Object-type InBlock, used for call() body mapping."""
        for b in self.in_blocks:
            if b.type == "Object":
                return b
        return self.in_blocks[0] if self.in_blocks else None

    @property
    def primary_in_block(self) -> str | None:
        """Name of the input block that kwargs are folded into.

        Prefers a block whose name starts with the TR code (e.g. ``t1101InBlock``),
        else the first Object-type block, else the first block.
        """
        for b in self.in_blocks:
            if b.name.lower().startswith(self.code.lower()):
                return b.name
        first = self.first_in_block()
        return first.name if first else None

    def build_body(self, params: dict | None = None, /, **kwargs: object) -> dict:
        """Build a request body by folding params/kwargs into the primary in-block.

        Example::

            spec.build_body(shcode="005930")
                -> {"t1101InBlock": {"shcode": "005930"}}
        """
        merged: dict[str, object] = {}
        if params:
            merged.update(params)
        merged.update(kwargs)

        block = self.primary_in_block
        if block is None:
            if merged:
                raise LSSpecError(f"TR {self.code} has no known input block but params were provided")
            return {}
        return {block: merged}


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


class Catalog:
    def __init__(self, index: dict, blocks: dict, catalog: list) -> None:
        self._index = index
        self._blocks = blocks
        self._catalog = catalog

    @classmethod
    def load(cls, specs_dir: Path | None = None) -> "Catalog":
        root = Path(specs_dir) if specs_dir else _SPECS_DIR
        try:
            index = json.loads((root / "index.json").read_text(encoding="utf-8"))
            blocks = json.loads((root / "blocks.json").read_text(encoding="utf-8"))
            catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise LSSpecError(f"spec 파일 없음 — build_specs.py를 먼저 실행하세요 ({exc})") from exc
        index = {k.strip(): v for k, v in index.items()}
        blocks = {k.strip(): v for k, v in blocks.items()}
        return cls(index=index, blocks=blocks, catalog=catalog)

    def tr(self, code: str) -> TRSpec:
        if code not in self._index:
            raise KeyError(f"알 수 없는 TR 코드: {code!r}")
        meta = self._index[code]
        blk = self._blocks.get(code, {})
        return TRSpec(
            code=code,
            name=meta["name"],
            group=meta["group"],
            category=meta["category"],
            method=meta.get("method", ""),
            url=meta.get("url", ""),
            domain=meta.get("domain", ""),
            content_type=meta.get("content_type", ""),
            tps_limit=meta.get("tps_limit"),
            in_blocks=_parse_blocks(blk.get("in_blocks", {})),
            out_blocks=_parse_blocks(blk.get("out_blocks", {})),
        )

    def has(self, code: str) -> bool:
        return code in self._index

    def codes(self) -> list[str]:
        return list(self._index.keys())

    def groups(self) -> list[dict]:
        return self._catalog

    def search(self, keyword: str) -> list[TRSpec]:
        """Return TRs whose code or name contains keyword."""
        kw = keyword.lower()
        return [self.tr(code) for code, meta in self._index.items() if kw in code.lower() or kw in meta.get("name", "").lower()]

    def find_by_group(self, keyword: str) -> list[TRSpec]:
        """Return TRs whose group name or category contains keyword."""
        kw = keyword.lower()
        return [self.tr(code) for code, meta in self._index.items() if kw in meta.get("group", "").lower() or kw in meta.get("category", "").lower()]


def _clean_block_name(name: str) -> str:
    """Strip the crawled ``(Occurs)`` array annotation from a block name.

    The catalog stores the documentation block names verbatim (e.g.
    ``"o3107InBlock\\n(Occurs)"``); the gateway expects the bare name. The
    repeating nature is already captured by ``BlockSpec.type == "Array"``.
    """
    return name.replace("(Occurs)", "").strip()


def _parse_blocks(raw: dict) -> tuple[BlockSpec, ...]:
    result = []
    for block_name, block_data in raw.items():
        block_name = _clean_block_name(block_name)
        fields = tuple(
            FieldSpec(
                name=f["name"],
                label=f.get("label", ""),
                type=f.get("type", "String"),
                length=f.get("length"),
                required=f.get("required", False),
                description=f.get("description", ""),
            )
            for f in block_data.get("fields", [])
        )
        result.append(BlockSpec(name=block_name, type=block_data.get("type", "Object"), fields=fields))
    return tuple(result)


@lru_cache(maxsize=1)
def default_catalog() -> Catalog:
    return Catalog.load()
