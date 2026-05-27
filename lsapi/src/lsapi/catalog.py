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
    label: str  # 한글명
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
        """첫 번째 Object 타입 InBlock (call() 바디 매핑용)."""
        for b in self.in_blocks:
            if b.type == "Object":
                return b
        return self.in_blocks[0] if self.in_blocks else None


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
        """TR 코드 또는 이름에 keyword가 포함된 TR 목록 반환."""
        kw = keyword.lower()
        return [self.tr(code) for code, meta in self._index.items() if kw in code.lower() or kw in meta.get("name", "").lower()]

    def find_by_group(self, keyword: str) -> list[TRSpec]:
        """그룹명 또는 카테고리에 keyword가 포함된 TR 목록 반환."""
        kw = keyword.lower()
        return [self.tr(code) for code, meta in self._index.items() if kw in meta.get("group", "").lower() or kw in meta.get("category", "").lower()]


def _parse_blocks(raw: dict) -> tuple[BlockSpec, ...]:
    result = []
    for block_name, block_data in raw.items():
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


# ---------------------------------------------------------------------------
# Real-time topic helpers
# ---------------------------------------------------------------------------


class _LazyTopicsDict:
    """카테고리별 실시간 TR 코드 목록. 첫 접근 시 catalog를 로드."""

    def __init__(self) -> None:
        self._data: dict[str, list[str]] | None = None

    def _load(self) -> dict[str, list[str]]:
        if self._data is None:
            cat = default_catalog()
            result: dict[str, list[str]] = {}
            for code in cat.codes():
                spec = cat.tr(code)
                if spec.is_realtime:
                    result.setdefault(spec.group, []).append(code)
            self._data = result
        return self._data

    def __getitem__(self, key: str) -> list[str]:
        return self._load()[key]

    def __iter__(self):
        return iter(self._load())

    def __repr__(self) -> str:
        return repr(self._load())

    def keys(self):
        return self._load().keys()

    def values(self):
        return self._load().values()

    def items(self):
        return self._load().items()


REALTIME_TOPICS: dict[str, list[str]] = _LazyTopicsDict()  # type: ignore[assignment]


def list_topics(category: str | None = None) -> list[TRSpec]:
    """실시간 TR 목록 반환.

    Args:
        category: 그룹명 키워드로 필터 (예: "주식", "선물"). None이면 전체 반환.

    Example:
        list_topics()             # 모든 실시간 TR
        list_topics("주식")       # 주식 관련 실시간 TR만
    """
    cat = default_catalog()
    topics = [cat.tr(code) for code in cat.codes() if cat.tr(code).is_realtime]
    if category:
        kw = category.lower()
        topics = [t for t in topics if kw in t.group.lower() or kw in t.category.lower()]
    return topics
