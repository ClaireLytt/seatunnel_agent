"""Value-level retrieval — indexing low-cardinality column values.

Schema retrieval only sees table/column *names and comments*; a question
like "华东地区的销售额" carries no lexical overlap with a column called
``region``. This module samples the distinct values of low-cardinality
string columns into an index, so cell values ("华东", "app", "已支付")
can pull in their table AND be quoted verbatim in the generated WHERE
clause (wrong literals are a top Text2SQL failure mode).

Build policy (bounded, deterministic):
- string-typed columns only, name not ending in ``id``/``_id``;
- at most ``max_columns`` per table, ``max_distinct`` values per column
  (columns exceeding it are high-cardinality — dropped);
- partitioned tables are skipped (an unpartitioned DISTINCT scan on a
  warehouse table is exactly what the validator exists to prevent);
- persisted to ``logs/.t2s_index/<schema_hash>.values.json`` keyed by the
  schema content hash, so re-connects reuse the index.

Builds run explicitly (CLI ``t2s-index-values``); sqlite sessions also
build on first use (local file, negligible cost). Set ``T2S_VALUE_INDEX=1``
to opt in to first-use auto-build on other engines, ``T2S_VALUE_INDEX=0``
to disable the index entirely.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .schema import SchemaStore

logger = logging.getLogger(__name__)

_INDEX_DIR = Path("logs") / ".t2s_index"

_STRING_TYPE_RE = re.compile(r"string|char|text", re.IGNORECASE)
_ID_LIKE_RE = re.compile(r"(?:^|_)id$", re.IGNORECASE)
_ENGLISH_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*")

MAX_DISTINCT = 50
MAX_COLUMNS_PER_TABLE = 10
MAX_VALUE_CHARS = 64
MAX_HITS = 10


@dataclass(frozen=True)
class ValueHit:
    table: str
    column: str
    value: str


def candidate_columns(table) -> list[str]:
    """Low-cardinality candidates: string-typed, not id-like."""
    out: list[str] = []
    for col in table.columns:
        if not _STRING_TYPE_RE.search(col.dtype):
            continue
        if _ID_LIKE_RE.search(col.name):
            continue
        out.append(col.name)
        if len(out) >= MAX_COLUMNS_PER_TABLE:
            break
    return out


@dataclass
class ValueIndex:
    """table -> column -> tuple of sampled distinct values."""

    data: dict[str, dict[str, tuple[str, ...]]] = field(default_factory=dict)

    def __len__(self) -> int:
        return sum(len(cols) for cols in self.data.values())

    # -- build -----------------------------------------------------------

    @classmethod
    def build(
        cls,
        executor,
        store: SchemaStore,
        max_distinct: int = MAX_DISTINCT,
    ) -> "ValueIndex":
        """Sample distinct values via the executor (one query per column)."""
        from .profiler import quote_identifier

        ds_type = getattr(
            getattr(executor, "config", None), "ds_type", "hive",
        )
        data: dict[str, dict[str, tuple[str, ...]]] = {}
        for table in store.tables:
            if table.is_partitioned:
                continue  # never full-scan a warehouse table for an index
            cols: dict[str, tuple[str, ...]] = {}
            for col in candidate_columns(table):
                q = quote_identifier(col, ds_type)
                if ds_type == "sqlserver":  # T-SQL has TOP, not LIMIT
                    sql = (
                        f"SELECT DISTINCT TOP {max_distinct + 1} {q} "
                        f"FROM {table.full_name} WHERE {q} IS NOT NULL"
                    )
                else:
                    sql = (
                        f"SELECT DISTINCT {q} FROM {table.full_name} "
                        f"WHERE {q} IS NOT NULL LIMIT {max_distinct + 1}"
                    )
                try:
                    result = executor.run(sql, max_rows=max_distinct + 1)
                except Exception as exc:
                    logger.debug("value sampling failed for %s.%s: %s",
                                 table.full_name, col, exc)
                    continue
                values = [
                    str(r[0])[:MAX_VALUE_CHARS] for r in result.rows
                    if r and r[0] is not None and str(r[0]).strip()
                ]
                if not values or len(values) > max_distinct:
                    continue  # empty or high-cardinality
                cols[col] = tuple(sorted(values))
            if cols:
                data[table.full_name] = cols
        return cls(data)

    # -- persistence -----------------------------------------------------

    @staticmethod
    def cache_path(schema_hash: str, index_dir: Path | None = None) -> Path:
        return (index_dir or _INDEX_DIR) / f"{schema_hash}.values.json"

    def save(self, schema_hash: str, index_dir: Path | None = None) -> Path:
        path = self.cache_path(schema_hash, index_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            t: {c: list(vs) for c, vs in cols.items()}
            for t, cols in self.data.items()
        }
        path.write_text(
            json.dumps({"schema_hash": schema_hash, "values": payload},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    @classmethod
    def load(
        cls, schema_hash: str, index_dir: Path | None = None,
    ) -> "ValueIndex | None":
        path = cls.cache_path(schema_hash, index_dir)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            values = raw.get("values", {})
            data = {
                str(t): {str(c): tuple(str(v) for v in vs)
                         for c, vs in cols.items()}
                for t, cols in values.items()
                if isinstance(cols, dict)
            }
            return cls(data)
        except (json.JSONDecodeError, OSError, AttributeError):
            return None

    # -- search ----------------------------------------------------------

    def search(self, query: str, max_hits: int = MAX_HITS) -> list[ValueHit]:
        """Values appearing in the question. CJK values match by substring
        (length >= 2); ASCII values match as whole case-insensitive tokens."""
        if not query.strip() or not self.data:
            return []
        query_lower = query.lower()
        query_tokens = {t.lower() for t in _ENGLISH_TOKEN_RE.findall(query)}
        hits: list[ValueHit] = []
        for table, cols in self.data.items():
            for col, values in cols.items():
                for v in values:
                    if len(v) < 2:
                        continue
                    if _ENGLISH_TOKEN_RE.fullmatch(v):
                        matched = v.lower() in query_tokens
                    elif v.isdigit():
                        # Digit-only values (status codes etc.) must stand
                        # alone — a substring match would fire on every
                        # date/number in the question ("2026-03-01" ⊃ "2026",
                        # so date separators count as word chars here).
                        matched = re.search(
                            rf"(?<![\w./:-]){re.escape(v)}(?![\w./:-])", query,
                        ) is not None
                    else:
                        matched = v in query or v.lower() in query_lower
                    if matched:
                        hits.append(ValueHit(table=table, column=col, value=v))
                        if len(hits) >= max_hits:
                            return hits
        return hits


def _auto_build_enabled(ds_type: str) -> bool:
    flag = os.getenv("T2S_VALUE_INDEX", "").strip()
    if flag == "0":
        return False
    if flag == "1" or flag.lower() == "auto":
        return True
    return ds_type == "sqlite"  # local file: negligible build cost


def load_or_build(runtime) -> ValueIndex | None:
    """The runtime's value index: cache when present, else auto-build where
    that's cheap/opted-in. Returns None when disabled or unavailable.
    Never raises — value retrieval is strictly additive."""
    if os.getenv("T2S_VALUE_INDEX", "").strip() == "0":
        return None
    try:
        from .retrieval import schema_hash

        h = schema_hash(runtime.store)
        cached = ValueIndex.load(h)
        if cached is not None:
            return cached
        if not _auto_build_enabled(runtime.ds_type):
            return None
        index = ValueIndex.build(runtime.executor, runtime.store)
        index.save(h)
        return index
    except Exception as exc:
        logger.debug("value index unavailable: %s", exc)
        return None
