"""Data comparison engine — deterministic schema / count / sample / aggregate diffs."""

from __future__ import annotations

import atexit
import json
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar

_log = logging.getLogger(__name__)
_POOL = ThreadPoolExecutor(max_workers=4)
atexit.register(_POOL.shutdown, wait=False)

_T = TypeVar("_T")
_U = TypeVar("_U")

_SAFE_IDENT = re.compile(r"^[\w][\w.$]*$", re.ASCII)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SchemaDiffItem:
    column: str
    status: str  # "added", "removed", "type_changed"
    type_a: str = ""
    type_b: str = ""


@dataclass
class SchemaDiffResult:
    table_a: str
    table_b: str
    items: list[SchemaDiffItem] = field(default_factory=list)
    cols_only_a: int = 0
    cols_only_b: int = 0
    type_changes: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.items)


@dataclass
class RowCountResult:
    table_a: str
    count_a: int
    table_b: str
    count_b: int
    delta: int = 0
    delta_pct: float = 0.0


@dataclass
class AggregateItem:
    column: str
    metric: str  # "sum", "avg", "min", "max", "null_count"
    value_a: Any = None
    value_b: Any = None
    match: bool = True


@dataclass
class AggregateResult:
    table_a: str
    table_b: str
    items: list[AggregateItem] = field(default_factory=list)
    mismatches: int = 0


@dataclass
class ModifiedRow:
    key: tuple
    changes: list[tuple[str, Any, Any]]  # (column, old_val, new_val)
    row_a: tuple | None = None
    row_b: tuple | None = None


@dataclass
class KeyedDiffResult:
    key_columns: list[str]
    columns: list[str]
    added: list[tuple] = field(default_factory=list)
    removed: list[tuple] = field(default_factory=list)
    modified: list[ModifiedRow] = field(default_factory=list)


@dataclass
class ProfileItem:
    column: str
    distinct_a: int = 0
    distinct_b: int = 0
    null_rate_a: float = 0.0
    null_rate_b: float = 0.0
    min_a: Any = None
    min_b: Any = None
    max_a: Any = None
    max_b: Any = None


@dataclass
class ProfileResult:
    table_a: str
    table_b: str
    total_a: int = 0
    total_b: int = 0
    items: list[ProfileItem] = field(default_factory=list)


@dataclass
class ThresholdConfig:
    value: float
    is_percentage: bool = True


@dataclass
class BatchFullItem:
    table_a: str
    table_b: str
    schema: SchemaDiffResult | None = None
    row_count: RowCountResult | None = None
    aggregate: AggregateResult | None = None
    has_diffs: bool = False


ColumnMapping = dict[str, str]


@dataclass
class QualityRule:
    column: str
    rule_type: str  # "not_null_rate", "unique_rate", "min_value", "max_value", "value_range", "expression"
    threshold: float = 0.0
    min_val: float | None = None
    max_val: float | None = None
    expression: str = ""


@dataclass
class QualityResult:
    rule: QualityRule
    actual_value: float
    passed: bool
    pending: bool = False


@dataclass
class ReportDiffItem:
    section: str
    field: str
    old_value: Any
    new_value: Any
    changed: bool


@dataclass
class ReportDiff:
    items: list[ReportDiffItem] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return any(i.changed for i in self.items)


@dataclass
class SkewBucket:
    value: str
    count_a: int = 0
    count_b: int = 0
    pct_a: float = 0.0
    pct_b: float = 0.0


@dataclass
class SkewItem:
    column: str
    gini_a: float = 0.0
    gini_b: float = 0.0
    cv_a: float = 0.0
    cv_b: float = 0.0
    top1_pct_a: float = 0.0
    top1_pct_b: float = 0.0
    ndv_a: int = 0
    ndv_b: int = 0
    buckets: list[SkewBucket] = field(default_factory=list)


@dataclass
class SkewResult:
    table_a: str
    table_b: str
    total_a: int = 0
    total_b: int = 0
    items: list[SkewItem] = field(default_factory=list)


@dataclass
class ChecksumItem:
    segment: int
    checksum_a: str
    checksum_b: str
    match: bool = True


@dataclass
class ChecksumResult:
    table_a: str
    table_b: str
    items: list[ChecksumItem] = field(default_factory=list)
    match_count: int = 0
    mismatch_count: int = 0


@dataclass
class PartitionCompareItem:
    partition_value: str
    count_a: int = 0
    count_b: int = 0
    delta: int = 0
    delta_pct: float = 0.0


@dataclass
class PartitionResult:
    table_a: str
    table_b: str
    partition_column: str = ""
    items: list[PartitionCompareItem] = field(default_factory=list)
    total_delta: int = 0


@dataclass
class CustomAggItem:
    expression: str
    alias: str
    value_a: float | None = None
    value_b: float | None = None
    match: bool = True


@dataclass
class CustomAggResult:
    table_a: str
    table_b: str
    items: list[CustomAggItem] = field(default_factory=list)
    mismatches: int = 0


@dataclass
class CompareReport:
    """Structured comparison report — source of truth for export."""
    schema: SchemaDiffResult | None = None
    row_count: RowCountResult | None = None
    sample: Any | None = None  # ResultDiff from text2sql.differ
    aggregate: AggregateResult | None = None
    batch_counts: list[RowCountResult] | None = None
    profile: ProfileResult | None = None
    keyed_diff: KeyedDiffResult | None = None
    batch_full: list[BatchFullItem] | None = None
    skew: SkewResult | None = None
    checksum: ChecksumResult | None = None
    partition: PartitionResult | None = None
    custom_agg: CustomAggResult | None = None
    elapsed_ms: int = 0

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        d = asdict(self)
        return json.loads(json.dumps(d, default=str))

    @staticmethod
    def _restore_items(data: dict | None, item_cls: type, container_cls: type):
        if not data:
            return None
        d = dict(data)
        items = [item_cls(**it) for it in d.pop("items", [])]
        return container_cls(**d, items=items)

    @classmethod
    def from_dict(cls, d: dict) -> "CompareReport":
        """Reconstruct from a dict produced by ``to_dict``.

        Safe to call multiple times on the same dict — input is never mutated.
        """
        _ri = cls._restore_items

        schema = _ri(d.get("schema"), SchemaDiffItem, SchemaDiffResult)

        row_count = RowCountResult(**d["row_count"]) if d.get("row_count") else None

        aggregate = _ri(d.get("aggregate"), AggregateItem, AggregateResult)

        batch_counts = None
        if d.get("batch_counts"):
            batch_counts = [RowCountResult(**rc) for rc in d["batch_counts"]]

        profile = _ri(d.get("profile"), ProfileItem, ProfileResult)

        keyed_diff = None
        if d.get("keyed_diff"):
            kd = dict(d["keyed_diff"])
            mods = []
            for m in kd.pop("modified", []):
                mods.append(ModifiedRow(
                    key=tuple(m["key"]),
                    changes=[tuple(c) for c in m["changes"]],
                    row_a=tuple(m["row_a"]) if m.get("row_a") else None,
                    row_b=tuple(m["row_b"]) if m.get("row_b") else None,
                ))
            added = [tuple(r) for r in kd.pop("added", [])]
            removed = [tuple(r) for r in kd.pop("removed", [])]
            keyed_diff = KeyedDiffResult(
                **kd, added=added, removed=removed, modified=mods,
            )

        batch_full = None
        if d.get("batch_full"):
            batch_full = []
            for bf in d["batch_full"]:
                bf_schema = _ri(bf.get("schema"), SchemaDiffItem, SchemaDiffResult)
                bf_rc = RowCountResult(**bf["row_count"]) if bf.get("row_count") else None
                bf_agg = _ri(bf.get("aggregate"), AggregateItem, AggregateResult)
                batch_full.append(BatchFullItem(
                    table_a=bf["table_a"], table_b=bf["table_b"],
                    schema=bf_schema, row_count=bf_rc, aggregate=bf_agg,
                    has_diffs=bf.get("has_diffs", False),
                ))

        skew = None
        if d.get("skew"):
            sk = dict(d["skew"])
            sitems = []
            for si in sk.pop("items", []):
                si_d = dict(si)
                buckets = [SkewBucket(**b) for b in si_d.pop("buckets", [])]
                sitems.append(SkewItem(**si_d, buckets=buckets))
            skew = SkewResult(**sk, items=sitems)

        checksum = _ri(d.get("checksum"), ChecksumItem, ChecksumResult)
        partition = _ri(d.get("partition"), PartitionCompareItem, PartitionResult)
        custom_agg = _ri(d.get("custom_agg"), CustomAggItem, CustomAggResult)

        return cls(
            schema=schema,
            row_count=row_count,
            sample=d.get("sample"),
            aggregate=aggregate,
            batch_counts=batch_counts,
            profile=profile,
            keyed_diff=keyed_diff,
            batch_full=batch_full,
            skew=skew,
            checksum=checksum,
            partition=partition,
            custom_agg=custom_agg,
            elapsed_ms=d.get("elapsed_ms", 0),
        )


# ---------------------------------------------------------------------------
# Identifier quoting
# ---------------------------------------------------------------------------

def quote_identifier(name: str) -> str:
    """Quote a SQL identifier to prevent injection.

    Simple names (alphanumeric + underscore/dot/$) pass through unchanged.
    Anything else is double-quoted with embedded quotes escaped.
    """
    if _SAFE_IDENT.match(name):
        return name
    return '"' + name.replace('"', '""') + '"'


# ---------------------------------------------------------------------------
# Schema comparison
# ---------------------------------------------------------------------------

def compare_schemas(
    cols_a: list[dict[str, str]],
    cols_b: list[dict[str, str]],
    table_a: str = "A",
    table_b: str = "B",
) -> SchemaDiffResult:
    """Compare two column lists and return structured diffs.

    Each column dict must have ``"name"`` and ``"type"`` keys.
    """
    map_a = {c["name"].lower(): c for c in cols_a}
    map_b = {c["name"].lower(): c for c in cols_b}

    items: list[SchemaDiffItem] = []
    only_a = only_b = type_chg = 0

    for key, ca in map_a.items():
        if key not in map_b:
            items.append(SchemaDiffItem(ca["name"], "removed", type_a=ca["type"]))
            only_a += 1
        else:
            cb = map_b[key]
            if ca["type"].lower() != cb["type"].lower():
                items.append(SchemaDiffItem(
                    ca["name"], "type_changed", type_a=ca["type"], type_b=cb["type"],
                ))
                type_chg += 1

    for key, cb in map_b.items():
        if key not in map_a:
            items.append(SchemaDiffItem(cb["name"], "added", type_b=cb["type"]))
            only_b += 1

    return SchemaDiffResult(
        table_a=table_a, table_b=table_b, items=items,
        cols_only_a=only_a, cols_only_b=only_b, type_changes=type_chg,
    )


# ---------------------------------------------------------------------------
# SQL builders
# ---------------------------------------------------------------------------

def _where_clause(where: str) -> str:
    return f" WHERE {where}" if where.strip() else ""


def _row_limit(ds_type: str, n: int) -> tuple[str, str]:
    if ds_type == "sqlserver":
        return f"TOP {int(n)} ", ""
    return "", f" LIMIT {int(n)}"


def build_count_sql(table_name: str, where: str = "") -> str:
    return f"SELECT COUNT(*) AS cnt FROM {quote_identifier(table_name)}{_where_clause(where)}"


def build_sample_sql(table_name: str, limit: int = 100, where: str = "",
                     ds_type: str = "mysql") -> str:
    top, tail = _row_limit(ds_type, limit)
    return f"SELECT {top}* FROM {quote_identifier(table_name)}{_where_clause(where)}{tail}"


_NUMERIC_KEYWORDS = frozenset({
    "int", "integer", "bigint", "smallint", "tinyint",
    "float", "double", "decimal", "numeric", "real", "number",
    "serial", "bigserial", "smallserial", "money",
})


def is_numeric_type(dtype: str) -> bool:
    """Check whether a column type string represents a numeric type."""
    base = dtype.lower().split("(")[0].strip()
    return base in _NUMERIC_KEYWORDS


def build_aggregate_sql(table_name: str, columns: list[str], where: str = "") -> str:
    """Build SQL to compute SUM/AVG/MIN/MAX and NULL count for *columns*."""
    if not columns:
        return build_count_sql(table_name, where)
    exprs: list[str] = ["COUNT(*) AS cnt"]
    if len(columns) > 20:
        _log.warning("Truncating columns from %d to 20 for aggregate SQL on %s", len(columns), table_name)
    for c in columns[:20]:
        qc = quote_identifier(c)
        exprs.append(f"SUM({qc}) AS {quote_identifier(c + '__sum')}")
        exprs.append(f"AVG({qc}) AS {quote_identifier(c + '__avg')}")
        exprs.append(f"MIN({qc}) AS {quote_identifier(c + '__min')}")
        exprs.append(f"MAX({qc}) AS {quote_identifier(c + '__max')}")
        exprs.append(f"SUM(CASE WHEN {qc} IS NULL THEN 1 ELSE 0 END) AS {quote_identifier(c + '__null')}")
    return ("SELECT " + ",\n       ".join(exprs)
            + f"\n  FROM {quote_identifier(table_name)}{_where_clause(where)}")


# ---------------------------------------------------------------------------
# Aggregate comparison
# ---------------------------------------------------------------------------

_METRIC_OFFSETS = {"sum": 0, "avg": 1, "min": 2, "max": 3, "null_count": 4}


def _close_enough(a: Any, b: Any, tolerance: float = 1e-6) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)
    if math.isnan(fa) and math.isnan(fb):
        return True
    if math.isnan(fa) or math.isnan(fb):
        return False
    if fa == fb:
        return True
    denom = max(abs(fa), abs(fb), 1e-9)
    return abs(fa - fb) / denom < tolerance


def compare_aggregates(
    table_a: str,
    row_a: tuple,
    table_b: str,
    row_b: tuple,
    columns: list[str],
    tolerance: float = 1e-6,
) -> AggregateResult:
    """Compare aggregate stats from SQL built by ``build_aggregate_sql``."""
    items: list[AggregateItem] = []
    mismatches = 0
    if len(columns) > 20:
        _log.warning("Truncating columns from %d to 20 for aggregate comparison on %s / %s", len(columns), table_a, table_b)
    for i, col in enumerate(columns[:20]):
        base = 1 + i * 5  # skip cnt at index 0
        for metric, offset in _METRIC_OFFSETS.items():
            idx = base + offset
            va = row_a[idx] if idx < len(row_a) else None
            vb = row_b[idx] if idx < len(row_b) else None
            ok = _close_enough(va, vb, tolerance)
            if not ok:
                mismatches += 1
            items.append(AggregateItem(
                column=col, metric=metric, value_a=va, value_b=vb, match=ok,
            ))
    return AggregateResult(
        table_a=table_a, table_b=table_b, items=items, mismatches=mismatches,
    )


# ---------------------------------------------------------------------------
# Batch table comparison helpers
# ---------------------------------------------------------------------------

def find_common_tables(
    tables_a: list[str], tables_b: list[str],
) -> list[tuple[str, str]]:
    """Find same-name tables across both sides (case-insensitive).

    Returns ``[(name_a, name_b), ...]`` preserving original casing.
    """
    map_b = {t.lower(): t for t in tables_b}
    pairs: list[tuple[str, str]] = []
    for ta in tables_a:
        tb = map_b.get(ta.lower())
        if tb is not None:
            pairs.append((ta, tb))
    return pairs


def build_row_count_result(
    table_a: str, count_a: int, table_b: str, count_b: int,
) -> RowCountResult:
    """Build a ``RowCountResult`` with computed delta/pct."""
    delta = count_a - count_b
    denom = max(count_a, count_b, 1)
    pct = delta / denom * 100
    return RowCountResult(table_a, count_a, table_b, count_b, delta, pct)


# ---------------------------------------------------------------------------
# Key-based row diff  (A)
# ---------------------------------------------------------------------------

def diff_by_key(
    cols_a: list[str],
    rows_a: list[tuple],
    cols_b: list[str],
    rows_b: list[tuple],
    key_cols: list[str],
    max_rows: int = 200,
) -> KeyedDiffResult:
    """Compare rows by primary key columns."""
    key_idx_a = [cols_a.index(k) for k in key_cols]
    key_idx_b = [cols_b.index(k) for k in key_cols]

    shared = [c for c in cols_a if c in cols_b]
    val_cols = [c for c in shared if c not in key_cols]

    shared_idx_a = [cols_a.index(c) for c in shared]
    shared_idx_b = [cols_b.index(c) for c in shared]
    val_idx_a = {vc: cols_a.index(vc) for vc in val_cols}
    val_idx_b = {vc: cols_b.index(vc) for vc in val_cols}

    map_a: dict[tuple, tuple] = {}
    for row in rows_a:
        key = tuple(row[i] for i in key_idx_a)
        map_a[key] = row

    map_b: dict[tuple, tuple] = {}
    for row in rows_b:
        key = tuple(row[i] for i in key_idx_b)
        map_b[key] = row

    added: list[tuple] = []
    removed: list[tuple] = []
    modified: list[ModifiedRow] = []

    for key, row_a in map_a.items():
        if key not in map_b:
            if len(removed) < max_rows:
                removed.append(tuple(row_a[i] for i in shared_idx_a))
        else:
            row_b = map_b[key]
            changes: list[tuple[str, Any, Any]] = []
            for vc in val_cols:
                va = row_a[val_idx_a[vc]]
                vb = row_b[val_idx_b[vc]]
                if not _close_enough(va, vb):
                    changes.append((vc, va, vb))
            if changes and len(modified) < max_rows:
                modified.append(ModifiedRow(key=key, changes=changes,
                                            row_a=row_a, row_b=row_b))

    for key, row_b in map_b.items():
        if key not in map_a:
            if len(added) < max_rows:
                added.append(tuple(row_b[i] for i in shared_idx_b))

    return KeyedDiffResult(
        key_columns=key_cols, columns=shared,
        added=added, removed=removed, modified=modified,
    )


# ---------------------------------------------------------------------------
# Column profile  (C)
# ---------------------------------------------------------------------------

def build_profile_sql(table_name: str, columns: list[str], where: str = "") -> str:
    """Build SQL to compute distinct count, null count, min, max per column."""
    if not columns:
        return build_count_sql(table_name, where)
    exprs: list[str] = ["COUNT(*) AS cnt"]
    if len(columns) > 20:
        _log.warning("Truncating columns from %d to 20 for profile SQL on %s", len(columns), table_name)
    for c in columns[:20]:
        qc = quote_identifier(c)
        exprs.append(f"COUNT(DISTINCT {qc}) AS {quote_identifier(c + '__dist')}")
        exprs.append(f"SUM(CASE WHEN {qc} IS NULL THEN 1 ELSE 0 END) AS {quote_identifier(c + '__null')}")
        exprs.append(f"MIN({qc}) AS {quote_identifier(c + '__min')}")
        exprs.append(f"MAX({qc}) AS {quote_identifier(c + '__max')}")
    return ("SELECT " + ",\n       ".join(exprs)
            + f"\n  FROM {quote_identifier(table_name)}{_where_clause(where)}")


def compare_profiles(
    table_a: str, row_a: tuple, total_a: int,
    table_b: str, row_b: tuple, total_b: int,
    columns: list[str],
) -> ProfileResult:
    """Compare column profiles from SQL built by ``build_profile_sql``."""
    items: list[ProfileItem] = []
    if len(columns) > 20:
        _log.warning("Truncating columns from %d to 20 for profile comparison on %s / %s", len(columns), table_a, table_b)
    for i, col in enumerate(columns[:20]):
        base = 1 + i * 4
        dist_a = row_a[base] if base < len(row_a) else 0
        null_a = row_a[base + 1] if base + 1 < len(row_a) else 0
        min_a = row_a[base + 2] if base + 2 < len(row_a) else None
        max_a = row_a[base + 3] if base + 3 < len(row_a) else None

        dist_b = row_b[base] if base < len(row_b) else 0
        null_b = row_b[base + 1] if base + 1 < len(row_b) else 0
        min_b = row_b[base + 2] if base + 2 < len(row_b) else None
        max_b = row_b[base + 3] if base + 3 < len(row_b) else None

        nr_a = (int(null_a) / total_a * 100) if total_a else 0.0
        nr_b = (int(null_b) / total_b * 100) if total_b else 0.0

        items.append(ProfileItem(
            column=col,
            distinct_a=int(dist_a or 0), distinct_b=int(dist_b or 0),
            null_rate_a=round(nr_a, 2), null_rate_b=round(nr_b, 2),
            min_a=min_a, min_b=min_b,
            max_a=max_a, max_b=max_b,
        ))
    return ProfileResult(
        table_a=table_a, table_b=table_b,
        total_a=total_a, total_b=total_b,
        items=items,
    )


# ---------------------------------------------------------------------------
# Concurrent execution helper  (F)
# ---------------------------------------------------------------------------

def run_parallel(fn_a: Callable[[], _T], fn_b: Callable[[], _U]) -> tuple[_T, _U]:
    """Run two callables concurrently, return (result_a, result_b)."""
    future_a = _POOL.submit(fn_a)
    future_b = _POOL.submit(fn_b)
    return future_a.result(), future_b.result()


# ---------------------------------------------------------------------------
# Threshold  (B)
# ---------------------------------------------------------------------------

def parse_threshold(raw: str) -> ThresholdConfig | None:
    """Parse '5%' or '100' into ThresholdConfig. Returns None if empty/invalid."""
    s = raw.strip()
    if not s:
        return None
    try:
        if s.endswith("%"):
            return ThresholdConfig(value=float(s[:-1]), is_percentage=True)
        return ThresholdConfig(value=float(s), is_percentage=False)
    except ValueError:
        return None


def check_row_count_threshold(result: RowCountResult, threshold: ThresholdConfig) -> bool:
    """Return True if row count delta is within threshold (pass)."""
    if threshold.is_percentage:
        return abs(result.delta_pct) <= threshold.value
    return abs(result.delta) <= threshold.value


def check_aggregate_threshold(result: AggregateResult, threshold: ThresholdConfig | None) -> bool:
    """Return True if all aggregates are within the threshold tolerance."""
    if threshold is None:
        return result.mismatches == 0
    for item in result.items:
        if item.value_a is None or item.value_b is None:
            continue
        try:
            va, vb = float(item.value_a), float(item.value_b)
        except (TypeError, ValueError):
            continue
        diff = abs(va - vb)
        if threshold.is_percentage:
            denom = max(abs(va), abs(vb), 1e-9)
            if diff / denom * 100 > threshold.value:
                return False
        else:
            if diff > threshold.value:
                return False
    return True


# ---------------------------------------------------------------------------
# Column mapping  (D)
# ---------------------------------------------------------------------------

def parse_column_mapping(raw: str) -> ColumnMapping:
    """Parse 'col_a:col_b, name:full_name' into {col_a: col_b}."""
    mapping: ColumnMapping = {}
    if not raw.strip():
        return mapping
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" not in pair:
            continue
        parts = pair.split(":", 1)
        a_col = parts[0].strip()
        b_col = parts[1].strip()
        if a_col and b_col:
            mapping[a_col] = b_col
    return mapping


def apply_column_mapping(columns: list[str], mapping: ColumnMapping) -> list[str]:
    """Remap column names: values in mapping are renamed to keys."""
    reverse = {v.lower(): k for k, v in mapping.items()}
    return [reverse.get(c.lower(), c) for c in columns]


# ---------------------------------------------------------------------------
# Random sampling SQL  (G)
# ---------------------------------------------------------------------------

_RANDOM_SQL: dict[str, str] = {
    "mysql":      "SELECT * FROM {table}{where} ORDER BY RAND() LIMIT {limit}",
    "postgresql": "SELECT * FROM {table}{where} ORDER BY RANDOM() LIMIT {limit}",
    "clickhouse": "SELECT * FROM {table}{where} ORDER BY rand() LIMIT {limit}",
    "doris":      "SELECT * FROM {table}{where} ORDER BY RAND() LIMIT {limit}",
    "hive":       "SELECT * FROM {table}{where} DISTRIBUTE BY RAND() SORT BY RAND() LIMIT {limit}",
    "sparksql":   "SELECT * FROM {table}{where} ORDER BY RAND() LIMIT {limit}",
    "sqlserver":  "SELECT TOP {limit} * FROM {table}{where} ORDER BY NEWID()",
    "flinksql":   "SELECT * FROM {table}{where} LIMIT {limit}",
}


def build_random_sample_sql(
    table_name: str, limit: int = 100, ds_type: str = "mysql", where: str = "",
) -> str:
    """Build dialect-specific random sampling SQL."""
    tpl = _RANDOM_SQL.get(ds_type, _RANDOM_SQL["mysql"])
    return tpl.format(
        table=quote_identifier(table_name),
        limit=int(limit),
        where=_where_clause(where),
    )


def build_stratified_sample_sql(
    table_name: str,
    group_col: str,
    sample_per_group: int = 10,
    ds_type: str = "mysql",
    where: str = "",
) -> str:
    """Build SQL for stratified sampling via ROW_NUMBER() OVER(PARTITION BY)."""
    qt = quote_identifier(table_name)
    qc = quote_identifier(group_col)
    wc = _where_clause(where)
    n = int(sample_per_group)
    return (
        f"SELECT * FROM ("
        f"SELECT *, ROW_NUMBER() OVER(PARTITION BY {qc} ORDER BY {qc}) AS _rn "
        f"FROM {qt}{wc}"
        f") _sub WHERE _rn <= {n}"
    )


# ---------------------------------------------------------------------------
# JDBC helpers  (C)
# ---------------------------------------------------------------------------

_JDBC_URL_PATTERNS: dict[str, str] = {
    "mysql":      "jdbc:mysql://{host}:{port}/{database}",
    "postgresql": "jdbc:postgresql://{host}:{port}/{database}",
    "sqlserver":  "jdbc:sqlserver://{host}:{port};databaseName={database}",
    "clickhouse": "jdbc:clickhouse://{host}:{port}/{database}",
    "doris":      "jdbc:mysql://{host}:{port}/{database}",
    "hive":       "jdbc:hive2://{host}:{port}/{database}",
    "sparksql":   "jdbc:hive2://{host}:{port}/{database}",
}

_JDBC_DRIVERS: dict[str, str] = {
    "mysql":      "com.mysql.cj.jdbc.Driver",
    "doris":      "com.mysql.cj.jdbc.Driver",
    "postgresql": "org.postgresql.Driver",
    "sqlserver":  "com.microsoft.sqlserver.jdbc.SQLServerDriver",
    "clickhouse": "com.clickhouse.jdbc.ClickHouseDriver",
    "hive":       "org.apache.hive.jdbc.HiveDriver",
    "sparksql":   "org.apache.hive.jdbc.HiveDriver",
}


def build_jdbc_url(ds_type: str, host: str, port: int, database: str) -> str:
    pattern = _JDBC_URL_PATTERNS.get(ds_type, "jdbc:{ds}://{host}:{port}/{database}")
    return pattern.format(ds=ds_type, host=host, port=port, database=database)


def get_jdbc_driver(ds_type: str) -> str:
    return _JDBC_DRIVERS.get(ds_type, "")


def _escape_hocon(s: str) -> str:
    """Escape a string value for embedding in a HOCON double-quoted string."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("$", "$$")


def generate_sync_config(
    ds_type_a: str, host_a: str, port_a: int, db_a: str,
    user_a: str | None, pwd_a: str | None, table_a: str,
    ds_type_b: str, host_b: str, port_b: int, db_b: str,
    user_b: str | None, pwd_b: str | None, table_b: str,
    column_mapping: ColumnMapping | None = None,
) -> str:
    """Generate a SeaTunnel HOCON sync job config: source A -> sink B."""
    url_a = build_jdbc_url(ds_type_a, host_a, port_a, db_a)
    url_b = build_jdbc_url(ds_type_b, host_b, port_b, db_b)
    drv_a = get_jdbc_driver(ds_type_a)
    drv_b = get_jdbc_driver(ds_type_b)

    transform_block = "transform {\n}"
    if column_mapping:
        field_list = ", ".join(
            f"{quote_identifier(v)} AS {quote_identifier(k)}"
            for k, v in column_mapping.items()
        )
        transform_block = (
            'transform {\n'
            '  Sql {\n'
            f'    query = "SELECT *, {field_list} FROM source_table"\n'
            '  }\n'
            '}'
        )

    lines = [
        'env {',
        '  job.mode = "BATCH"',
        '  parallelism = 2',
        '}',
        '',
        'source {',
        '  Jdbc {',
        f'    url = "{url_a}"',
        f'    driver = "{drv_a}"',
    ]
    if user_a:
        lines.append(f'    user = "{_escape_hocon(user_a)}"')
    if pwd_a:
        lines.append(f'    password = "{_escape_hocon(pwd_a)}"')
    lines += [
        f'    query = "SELECT * FROM {quote_identifier(table_a)}"',
        '  }',
        '}',
        '',
        transform_block,
        '',
        'sink {',
        '  Jdbc {',
        f'    url = "{url_b}"',
        f'    driver = "{drv_b}"',
    ]
    if user_b:
        lines.append(f'    user = "{_escape_hocon(user_b)}"')
    if pwd_b:
        lines.append(f'    password = "{_escape_hocon(pwd_b)}"')
    lines += [
        f'    database = "{db_b}"',
        f'    table = "{table_b}"',
        '    generate_sink_sql = true',
        '  }',
        '}',
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Trend data  (H)
# ---------------------------------------------------------------------------

def build_trend_data(
    reports_dir: Path,
) -> list[dict[str, Any]]:
    """Read saved reports and extract time-series delta data.

    Returns a list of dicts with keys: timestamp, table_a, table_b, delta,
    delta_pct, mismatches, schema_changes.
    """
    if not reports_dir.is_dir():
        return []

    entries: list[dict[str, Any]] = []
    for fpath in sorted(reports_dir.glob("compare_*.json")):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                d = json.load(f)
            ts = fpath.stem.replace("compare_", "")
            report = CompareReport.from_dict(d)
            if report.row_count:
                entries.append({
                    "timestamp": ts,
                    "table_a": report.row_count.table_a,
                    "table_b": report.row_count.table_b,
                    "delta": report.row_count.delta,
                    "delta_pct": report.row_count.delta_pct,
                    "mismatches": report.aggregate.mismatches if report.aggregate else 0,
                    "schema_changes": len(report.schema.items) if report.schema else 0,
                })
        except Exception:
            _log.warning(
                "Skipping corrupt report: %s", fpath, exc_info=True)
            continue
    return entries


# ---------------------------------------------------------------------------
# Incremental comparison SQL  (A)
# ---------------------------------------------------------------------------

def build_incremental_sql(
    table_name: str, watermark_col: str, last_value: str,
    limit: int = 1000, where: str = "", ds_type: str = "mysql",
) -> str:
    """Build SQL that fetches only rows newer than *last_value*."""
    tbl = quote_identifier(table_name)
    wm = quote_identifier(watermark_col)
    parts: list[str] = []
    if last_value:
        parts.append(f"{wm} > {_sql_literal(last_value)}")
    w = where.strip()
    if w:
        parts.append(f"({w})")
    clause = (" WHERE " + " AND ".join(parts)) if parts else ""
    top, tail = _row_limit(ds_type, limit)
    return f"SELECT {top}* FROM {tbl}{clause} ORDER BY {wm}{tail}"


# ---------------------------------------------------------------------------
# Data quality rules  (B)
# ---------------------------------------------------------------------------

def parse_quality_rules(raw: str) -> list[QualityRule]:
    """Parse rules like ``name:not_null>95, age:range:0-150, id:unique>99``."""
    rules: list[QualityRule] = []
    if not raw.strip():
        return rules
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            if ":range:" in token:
                col, _, bounds = token.partition(":range:")
                lo, hi = bounds.split("-", 1)
                rules.append(QualityRule(
                    column=col.strip(), rule_type="value_range",
                    min_val=float(lo), max_val=float(hi)))
            elif ":not_null>" in token:
                col, _, val = token.partition(":not_null>")
                rules.append(QualityRule(
                    column=col.strip(), rule_type="not_null_rate",
                    threshold=float(val)))
            elif ":unique>" in token:
                col, _, val = token.partition(":unique>")
                rules.append(QualityRule(
                    column=col.strip(), rule_type="unique_rate",
                    threshold=float(val)))
            elif ":min>" in token:
                col, _, val = token.partition(":min>")
                rules.append(QualityRule(
                    column=col.strip(), rule_type="min_value",
                    threshold=float(val)))
            elif ":max<" in token:
                col, _, val = token.partition(":max<")
                rules.append(QualityRule(
                    column=col.strip(), rule_type="max_value",
                    threshold=float(val)))
            elif ":expr:" in token:
                col, _, expr = token.partition(":expr:")
                rules.append(QualityRule(
                    column=col.strip(), rule_type="expression",
                    expression=expr.strip()))
        except (ValueError, IndexError):
            continue
    return rules


def check_quality_rules(
    rules: list[QualityRule], profile: ProfileResult,
) -> list[QualityResult]:
    """Evaluate quality rules against profile data from Source A."""
    results: list[QualityResult] = []
    item_map = {it.column.lower(): it for it in profile.items}
    for rule in rules:
        item = item_map.get(rule.column.lower())
        if item is None:
            results.append(QualityResult(rule=rule, actual_value=0.0, passed=False))
            continue
        if rule.rule_type == "not_null_rate":
            actual = 100.0 - item.null_rate_a
            results.append(QualityResult(rule=rule, actual_value=actual,
                                         passed=actual >= rule.threshold))
        elif rule.rule_type == "unique_rate":
            total = profile.total_a or 1
            actual = item.distinct_a / total * 100.0
            results.append(QualityResult(rule=rule, actual_value=actual,
                                         passed=actual >= rule.threshold))
        elif rule.rule_type == "min_value":
            try:
                actual = float(item.min_a) if item.min_a is not None else 0.0
            except (TypeError, ValueError):
                actual = 0.0
            results.append(QualityResult(rule=rule, actual_value=actual,
                                         passed=actual >= rule.threshold))
        elif rule.rule_type == "max_value":
            try:
                actual = float(item.max_a) if item.max_a is not None else 0.0
            except (TypeError, ValueError):
                actual = 0.0
            results.append(QualityResult(rule=rule, actual_value=actual,
                                         passed=actual <= rule.threshold))
        elif rule.rule_type == "value_range":
            try:
                lo = float(item.min_a) if item.min_a is not None else 0.0
            except (TypeError, ValueError):
                lo = 0.0
            try:
                hi = float(item.max_a) if item.max_a is not None else 0.0
            except (TypeError, ValueError):
                hi = 0.0
            passed = (rule.min_val is None or lo >= rule.min_val) and \
                     (rule.max_val is None or hi <= rule.max_val)
            results.append(QualityResult(rule=rule, actual_value=lo,
                                         passed=passed))
        elif rule.rule_type == "expression":
            results.append(QualityResult(
                rule=rule, actual_value=0.0, passed=False, pending=True))
    return results


# ---------------------------------------------------------------------------
# Diff → SQL generation  (C)
# ---------------------------------------------------------------------------

def _sql_literal(value: Any) -> str:
    """Format a Python value as a SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return "NULL"
        return str(value)
    s = str(value).replace("\\", "\\\\").replace("'", "''")
    return f"'{s}'"


def generate_diff_sql(
    keyed_diff: KeyedDiffResult, table_target: str,
    ds_type: str = "mysql",
) -> str:
    """Generate INSERT/UPDATE/DELETE SQL from a keyed diff result."""
    stmts: list[str] = []
    tbl = quote_identifier(table_target)
    cols = keyed_diff.columns
    key_cols = keyed_diff.key_columns
    col_set = set(cols)

    for row in keyed_diff.added:
        col_names = ", ".join(quote_identifier(c) for c in cols)
        values = ", ".join(_sql_literal(row[i]) if i < len(row) else "NULL"
                           for i in range(len(cols)))
        stmts.append(f"INSERT INTO {tbl} ({col_names}) VALUES ({values});")

    for row in keyed_diff.removed:
        wheres = []
        for kc in key_cols:
            if kc not in col_set:
                continue
            idx = cols.index(kc)
            wheres.append(f"{quote_identifier(kc)} = {_sql_literal(row[idx] if idx < len(row) else None)}")
        if wheres:
            stmts.append(f"DELETE FROM {tbl} WHERE {' AND '.join(wheres)};")

    for mod in keyed_diff.modified:
        sets = []
        for col, _old, new in mod.changes:
            sets.append(f"{quote_identifier(col)} = {_sql_literal(new)}")
        wheres = []
        for i, kc in enumerate(key_cols):
            wheres.append(f"{quote_identifier(kc)} = {_sql_literal(mod.key[i])}")
        stmts.append(f"UPDATE {tbl} SET {', '.join(sets)} WHERE {' AND '.join(wheres)};")

    return "\n".join(stmts)


# ---------------------------------------------------------------------------
# Data masking  (G)
# ---------------------------------------------------------------------------

_SENSITIVE_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"\b\d{3}[-.]?\d{3,4}[-.]?\d{4}\b"),
    "id_number": re.compile(r"\b\d{15,18}[xX]?\b"),
    "credit_card": re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
}


def detect_sensitive_columns(
    columns: list[str], sample_rows: list[tuple], max_scan: int = 20,
) -> dict[str, str]:
    """Scan sample data and return ``{column: mask_type}`` for PII columns."""
    result: dict[str, str] = {}
    scan = sample_rows[:max_scan]
    for ci, col in enumerate(columns):
        for row in scan:
            if ci >= len(row):
                continue
            val = row[ci]
            if val is None:
                continue
            s = str(val)
            for ptype, pat in _SENSITIVE_PATTERNS.items():
                if pat.search(s):
                    result[col] = ptype
                    break
            if col in result:
                break
    return result


def mask_value(value: Any, mask_type: str) -> str:
    """Mask a single value according to its sensitivity type."""
    if value is None:
        return "***"
    s = str(value)
    if mask_type == "email" and "@" in s:
        local, _, domain = s.partition("@")
        parts = domain.rsplit(".", 1)
        dom = parts[0] if parts else domain
        tld = ("." + parts[1]) if len(parts) > 1 else ""
        return f"{local[0]}***@{dom[0]}***{tld}"
    if mask_type == "phone" and len(s) >= 7:
        return s[:3] + "****" + s[-4:]
    if mask_type == "id_number" and len(s) >= 7:
        return s[:3] + "*" * (len(s) - 7) + s[-4:]
    if mask_type == "credit_card":
        digits = re.sub(r"[^0-9]", "", s)
        if len(digits) >= 4:
            return "**** **** **** " + digits[-4:]
    return "***"


def mask_rows(
    columns: list[str], rows: list[tuple], sensitive_cols: dict[str, str],
) -> list[tuple]:
    """Return rows with sensitive columns masked."""
    if not sensitive_cols:
        return rows
    col_lower = {c.lower(): i for i, c in enumerate(columns)}
    mask_idx: dict[int, str] = {}
    for col, mtype in sensitive_cols.items():
        idx = col_lower.get(col.lower())
        if idx is not None:
            mask_idx[idx] = mtype
    if not mask_idx:
        return rows
    out: list[tuple] = []
    for row in rows:
        new_row = list(row)
        for idx, mtype in mask_idx.items():
            if idx < len(new_row):
                new_row[idx] = mask_value(new_row[idx], mtype)
        out.append(tuple(new_row))
    return out


# ---------------------------------------------------------------------------
# Data skew analysis  (BB)
# ---------------------------------------------------------------------------

def build_skew_sql(
    table_name: str, column: str, where: str = "", top_n: int = 20,
    ds_type: str = "mysql",
) -> str:
    """Build SQL to get top-N value frequencies for one column."""
    qc = quote_identifier(column)
    qt = quote_identifier(table_name)
    if top_n > 0 and ds_type == "sqlserver":
        top_clause = f"TOP {int(top_n)} "
    else:
        top_clause = ""
    sql = (
        f"SELECT {top_clause}CAST({qc} AS VARCHAR(200)) AS val, COUNT(*) AS cnt"
        f"\n  FROM {qt}{_where_clause(where)}"
        f"\n GROUP BY {qc}"
        f"\n ORDER BY cnt DESC"
    )
    if top_n > 0 and ds_type != "sqlserver":
        sql += f"\n LIMIT {top_n}"
    return sql


def compute_skew_metrics(counts: list[int]) -> tuple[float, float, float]:
    """Return (gini, cv, top1_pct) from a list of frequency counts.

    - gini: 0 = uniform, 1 = all in one value
    - cv: coefficient of variation (std/mean)
    - top1_pct: percentage held by largest value
    """
    if not counts:
        return 0.0, 0.0, 0.0
    total = sum(counts)
    if total == 0:
        return 0.0, 0.0, 0.0
    n = len(counts)
    if n == 1:
        return 0.0, 0.0, 100.0

    # Gini coefficient
    sorted_c = sorted(counts)
    cum = 0.0
    weighted_sum = 0.0
    for i, c in enumerate(sorted_c):
        cum += c
        weighted_sum += (2 * (i + 1) - n - 1) * c
    gini = weighted_sum / (n * total) if total else 0.0
    gini = max(0.0, min(1.0, gini))

    # CV
    mean = total / n
    variance = sum((c - mean) ** 2 for c in counts) / n
    std = math.sqrt(variance)
    cv = std / mean if mean else 0.0

    # Top-1 concentration
    top1 = max(counts) / total * 100

    return round(gini, 4), round(cv, 4), round(top1, 2)


def compare_skew(
    table_a: str, table_b: str, column: str,
    rows_a: list[tuple], total_a: int,
    rows_b: list[tuple], total_b: int,
    top_n: int = 20,
) -> SkewItem:
    """Compare skew for one column between two tables."""
    counts_a = [int(r[1]) for r in rows_a if len(r) >= 2]
    counts_b = [int(r[1]) for r in rows_b if len(r) >= 2]

    gini_a, cv_a, top1_a = compute_skew_metrics(counts_a)
    gini_b, cv_b, top1_b = compute_skew_metrics(counts_b)

    # Merge buckets from both sides
    map_a: dict[str, int] = {}
    for r in rows_a:
        if len(r) >= 2:
            map_a[str(r[0])] = int(r[1])
    map_b: dict[str, int] = {}
    for r in rows_b:
        if len(r) >= 2:
            map_b[str(r[0])] = int(r[1])

    all_vals: list[str] = []
    seen: set[str] = set()
    for r in rows_a:
        v = str(r[0]) if len(r) >= 1 else ""
        if v not in seen:
            all_vals.append(v)
            seen.add(v)
    for r in rows_b:
        v = str(r[0]) if len(r) >= 1 else ""
        if v not in seen:
            all_vals.append(v)
            seen.add(v)

    buckets: list[SkewBucket] = []
    for v in all_vals[:top_n]:
        ca = map_a.get(v, 0)
        cb = map_b.get(v, 0)
        buckets.append(SkewBucket(
            value=v,
            count_a=ca, count_b=cb,
            pct_a=round(ca / total_a * 100, 2) if total_a else 0.0,
            pct_b=round(cb / total_b * 100, 2) if total_b else 0.0,
        ))

    return SkewItem(
        column=column,
        gini_a=gini_a, gini_b=gini_b,
        cv_a=cv_a, cv_b=cv_b,
        top1_pct_a=top1_a, top1_pct_b=top1_b,
        ndv_a=len(map_a), ndv_b=len(map_b),
        buckets=buckets,
    )


# ---------------------------------------------------------------------------
# Checksum comparison  (F1)
# ---------------------------------------------------------------------------

_HASH_FUNC: dict[str, str] = {
    "mysql":      "MD5(CONCAT_WS(',', {cols}))",
    "postgresql": "MD5(CONCAT_WS(',', {cols}))",
    "hive":       "MD5(CONCAT_WS(',', {cols}))",
    "sparksql":   "MD5(CONCAT_WS(',', {cols}))",
    "clickhouse": "MD5(CONCAT(toString({cols_ts})))",
    "doris":      "MD5(CONCAT_WS(',', {cols}))",
    "flinksql":   "MD5(CONCAT_WS(',', {cols}))",
    "sqlserver":  "HASHBYTES('MD5', CONCAT_WS(',', {cols}))",
}


def build_checksum_sql(
    table_name: str, columns: list[str], ds_type: str = "mysql",
    where: str = "", segments: int = 10,
) -> str:
    """Build SQL to compute per-segment checksums for data verification."""
    segments = max(1, int(segments))
    qt = quote_identifier(table_name)
    cols_quoted = ", ".join(f"CAST({quote_identifier(c)} AS VARCHAR(200))" for c in columns)

    tpl = _HASH_FUNC.get(ds_type, _HASH_FUNC["mysql"])
    if ds_type == "clickhouse":
        cols_ts = ", ".join(f"toString({quote_identifier(c)})" for c in columns)
        hash_expr = tpl.format(cols=cols_quoted, cols_ts=cols_ts)
    else:
        hash_expr = tpl.format(cols=cols_quoted)

    if ds_type in ("mysql", "postgresql", "clickhouse", "doris"):
        seg_expr = f"MOD(ABS(CRC32(CONCAT_WS(',', {cols_quoted}))), {segments})"
    else:
        seg_expr = f"ABS(CHECKSUM(CONCAT_WS(',', {cols_quoted}))) % {segments}"

    return (
        f"SELECT {seg_expr} AS seg,"
        f"\n  COUNT(*) AS cnt,"
        f"\n  MIN({hash_expr}) AS seg_hash"
        f"\n  FROM {qt}{_where_clause(where)}"
        f"\n GROUP BY {seg_expr}"
        f"\n ORDER BY seg"
    )


def compare_checksums(
    table_a: str, table_b: str,
    rows_a: list[tuple], rows_b: list[tuple],
) -> ChecksumResult:
    """Compare per-segment checksums from both sides."""
    map_a: dict[int, tuple[int, str]] = {}
    for r in rows_a:
        if len(r) >= 3:
            map_a[int(r[0])] = (int(r[1]), str(r[2]).lower())
    map_b: dict[int, tuple[int, str]] = {}
    for r in rows_b:
        if len(r) >= 3:
            map_b[int(r[0])] = (int(r[1]), str(r[2]).lower())

    all_segs = sorted(set(map_a.keys()) | set(map_b.keys()))
    items: list[ChecksumItem] = []
    match_count = 0
    mismatch_count = 0
    for seg in all_segs:
        a = map_a.get(seg, (0, ""))
        b = map_b.get(seg, (0, ""))
        matched = (a[0] == b[0] and a[1] == b[1])
        if matched:
            match_count += 1
        else:
            mismatch_count += 1
        items.append(ChecksumItem(
            segment=seg, checksum_a=a[1], checksum_b=b[1], match=matched,
        ))

    return ChecksumResult(
        table_a=table_a, table_b=table_b,
        items=items, match_count=match_count, mismatch_count=mismatch_count,
    )


# ---------------------------------------------------------------------------
# Partition-level comparison  (F2)
# ---------------------------------------------------------------------------

def build_partition_count_sql(
    table_name: str, partition_col: str, where: str = "",
    ds_type: str = "mysql",
) -> str:
    """Build SQL to get row counts grouped by partition column."""
    qt = quote_identifier(table_name)
    qp = quote_identifier(partition_col)
    return (
        f"SELECT CAST({qp} AS VARCHAR(200)) AS part_val, COUNT(*) AS cnt"
        f"\n  FROM {qt}{_where_clause(where)}"
        f"\n GROUP BY {qp}"
        f"\n ORDER BY cnt DESC"
    )


def compare_partitions(
    table_a: str, table_b: str, partition_col: str,
    rows_a: list[tuple], rows_b: list[tuple],
) -> PartitionResult:
    """Compare row counts per partition value."""
    map_a: dict[str, int] = {}
    for r in rows_a:
        if len(r) >= 2:
            map_a[str(r[0])] = int(r[1])
    map_b: dict[str, int] = {}
    for r in rows_b:
        if len(r) >= 2:
            map_b[str(r[0])] = int(r[1])

    all_keys = list(dict.fromkeys(
        [str(r[0]) for r in rows_a if len(r) >= 1] +
        [str(r[0]) for r in rows_b if len(r) >= 1]
    ))

    items: list[PartitionCompareItem] = []
    total_delta = 0
    for k in all_keys:
        ca = map_a.get(k, 0)
        cb = map_b.get(k, 0)
        delta = ca - cb
        total_delta += abs(delta)
        pct = round(delta / max(ca, cb, 1) * 100, 2)
        items.append(PartitionCompareItem(
            partition_value=k, count_a=ca, count_b=cb,
            delta=delta, delta_pct=pct,
        ))

    return PartitionResult(
        table_a=table_a, table_b=table_b,
        partition_column=partition_col,
        items=items, total_delta=total_delta,
    )


# ---------------------------------------------------------------------------
# Custom aggregate expressions  (F3)
# ---------------------------------------------------------------------------

_CUSTOM_AGG_FORBIDDEN = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|GRANT|REVOKE"
    r"|MERGE|CALL|UNION|SET|LOAD|COPY|RENAME)\b"
    r"|INTO\s+OUTFILE|;",
    re.IGNORECASE,
)


def parse_custom_agg_expressions(raw: str) -> list[tuple[str, str]]:
    """Parse ``alias=EXPRESSION`` lines, returning (alias, expr) pairs."""
    result: list[tuple[str, str]] = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        alias, _, expr = line.partition("=")
        alias = alias.strip()
        expr = expr.strip()
        if not alias or not expr:
            continue
        if _CUSTOM_AGG_FORBIDDEN.search(expr):
            continue
        result.append((alias, expr))
    return result


def build_custom_agg_sql(
    table_name: str, expressions: list[tuple[str, str]], where: str = "",
) -> str:
    """Build SQL with user-defined aggregate expressions."""
    qt = quote_identifier(table_name)
    parts = [f"({expr}) AS {quote_identifier(alias)}" for alias, expr in expressions]
    return f"SELECT {', '.join(parts)}\n  FROM {qt}{_where_clause(where)}"


def compare_custom_aggs(
    table_a: str, row_a: tuple, table_b: str, row_b: tuple,
    expressions: list[tuple[str, str]],
) -> CustomAggResult:
    """Compare custom aggregate results."""
    items: list[CustomAggItem] = []
    mismatches = 0
    for i, (alias, expr) in enumerate(expressions):
        va = float(row_a[i]) if i < len(row_a) and row_a[i] is not None else None
        vb = float(row_b[i]) if i < len(row_b) and row_b[i] is not None else None
        matched = _close_enough(va, vb)
        if not matched:
            mismatches += 1
        items.append(CustomAggItem(
            expression=expr, alias=alias,
            value_a=va, value_b=vb, match=matched,
        ))
    return CustomAggResult(
        table_a=table_a, table_b=table_b,
        items=items, mismatches=mismatches,
    )


# ---------------------------------------------------------------------------
# Trend alerting  (F4)
# ---------------------------------------------------------------------------


@dataclass
class AlertRule:
    """Parsed alert rule from user input."""
    metric: str
    threshold: float
    consecutive: int


@dataclass
class TrendAlert:
    """A single alert rule evaluation result."""
    metric: str
    threshold: float
    consecutive_required: int
    consecutive_actual: int
    triggered: bool
    current_value: float | None = None


def parse_alert_rules(raw: str) -> list[AlertRule]:
    """Parse alert rules from a string like ``row_count_delta>100:3, mismatches>0:5``.

    Each rule: ``metric>threshold:consecutive_count``
    """
    rules: list[AlertRule] = []
    for line in raw.replace(",", "\n").strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            left, consecutive_str = line.rsplit(":", 1)
            consecutive = int(consecutive_str)
            if ">" in left:
                metric, threshold_str = left.split(">", 1)
                rules.append(AlertRule(
                    metric=metric.strip(),
                    threshold=float(threshold_str),
                    consecutive=max(1, consecutive),
                ))
        except (ValueError, IndexError):
            continue
    return rules


def check_trend_alerts(
    trend_data: list[dict[str, Any]],
    alert_rules: list[AlertRule],
) -> list[TrendAlert]:
    """Check trend data against alert rules.

    *trend_data* is the output of ``build_trend_data()``.
    """
    _metric_extractors: dict[str, str] = {
        "row_count_delta": "delta",
        "delta": "delta",
        "delta_pct": "delta_pct",
        "mismatches": "mismatches",
    }

    results: list[TrendAlert] = []
    for rule in alert_rules:
        metric = rule.metric
        threshold = rule.threshold
        required = rule.consecutive
        field = _metric_extractors.get(metric, metric)

        consecutive = 0
        current_val: float | None = None
        for entry in reversed(trend_data):
            val = entry.get(field)
            if val is None:
                break
            current_val = current_val if current_val is not None else float(val)
            if abs(float(val)) > threshold:
                consecutive += 1
            else:
                break

        results.append(TrendAlert(
            metric=metric,
            threshold=threshold,
            consecutive_required=required,
            consecutive_actual=consecutive,
            triggered=consecutive >= required,
            current_value=current_val,
        ))
    return results


# ---------------------------------------------------------------------------
# Report diff — compare two CompareReport objects  (Phase 5A)
# ---------------------------------------------------------------------------

def diff_reports(old: CompareReport, new: CompareReport) -> ReportDiff:
    items: list[ReportDiffItem] = []

    old_delta = old.row_count.delta if old.row_count else None
    new_delta = new.row_count.delta if new.row_count else None
    items.append(ReportDiffItem(
        "row_count", "delta", old_delta, new_delta, old_delta != new_delta,
    ))

    old_schema = len(old.schema.items) if old.schema else 0
    new_schema = len(new.schema.items) if new.schema else 0
    items.append(ReportDiffItem(
        "schema", "change_count", old_schema, new_schema, old_schema != new_schema,
    ))

    old_agg = old.aggregate.mismatches if old.aggregate else 0
    new_agg = new.aggregate.mismatches if new.aggregate else 0
    items.append(ReportDiffItem(
        "aggregate", "mismatches", old_agg, new_agg, old_agg != new_agg,
    ))

    old_cksum = old.checksum.mismatch_count if old.checksum else 0
    new_cksum = new.checksum.mismatch_count if new.checksum else 0
    items.append(ReportDiffItem(
        "checksum", "mismatch_count", old_cksum, new_cksum, old_cksum != new_cksum,
    ))

    return ReportDiff(items=items)


# ---------------------------------------------------------------------------
# Custom expression quality rules  (Phase 5B)
# ---------------------------------------------------------------------------

def build_expression_check_sql(
    table: str, expression: str, where: str = "",
) -> str:
    tbl = quote_identifier(table)
    w = f" WHERE {where}" if where.strip() else ""
    return (
        f"SELECT COUNT(*) AS total, "
        f"SUM(CASE WHEN {expression} THEN 1 ELSE 0 END) AS passing "
        f"FROM {tbl}{w}"
    )


# ---------------------------------------------------------------------------
# Data lineage integration  (Phase 5C)
# ---------------------------------------------------------------------------

def get_upstream_tables(table_name: str, sql_list: list[str]) -> list[str]:
    from ..text2sql.lineage import trace_lineage

    seen: set[str] = set()
    target_lower = table_name.lower()
    for sql in sql_list:
        lineage = trace_lineage(sql)
        for t in lineage.source_tables:
            if t.lower() != target_lower and t.lower() not in seen:
                seen.add(t.lower())
    return sorted(seen)
