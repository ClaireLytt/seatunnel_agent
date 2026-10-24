"""Data comparison engine — deterministic schema / count / sample / aggregate diffs."""

from __future__ import annotations

import atexit
import json
import logging
import math
import os
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypeVar

_log = logging.getLogger(__name__)

try:
    _POOL_WORKERS = max(1, int(os.getenv("DC_POOL_WORKERS", "4")))
except ValueError:
    _POOL_WORKERS = 4
_POOL = ThreadPoolExecutor(max_workers=_POOL_WORKERS)
atexit.register(_POOL.shutdown, wait=False)

_T = TypeVar("_T")
_U = TypeVar("_U")

from .models import (  # noqa: F401 — re-exported, public API
    AggregateItem,
    AggregateResult,
    BatchFullItem,
    ChecksumItem,
    ChecksumResult,
    ColumnMapping,
    CompareReport,
    CustomAggItem,
    CustomAggResult,
    KeyedDiffResult,
    ModifiedRow,
    PartitionCompareItem,
    PartitionResult,
    ProfileItem,
    ProfileResult,
    QualityResult,
    QualityRule,
    ReportDiff,
    ReportDiffItem,
    RowCountResult,
    SchemaDiffItem,
    SchemaDiffResult,
    SkewBucket,
    SkewItem,
    SkewResult,
    ThresholdConfig,
)
from .sqlbase import (  # noqa: F401 — re-exported, public API
    _BACKSLASH_ESCAPE_DIALECTS,
    DEFAULT_CHECKSUM_SEGMENTS,
    GINI_MISMATCH_THRESHOLD,
    GINI_SKEW_THRESHOLD,
    MAX_AGG_COLUMNS,
    STR_CAST_LEN,
    TOP1_MISMATCH_PP,
    TOP1_SKEW_THRESHOLD,
    _blank_string_literals,
    _canon_timestamp,
    _close_enough,
    _row_limit,
    _where_clause,
    cast_to_string,
    quote_identifier,
    validate_where,
)

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


def build_aggregate_sql(table_name: str, columns: list[str], where: str = "",
                        ds_type: str = "") -> str:
    """Build SQL to compute SUM/AVG/MIN/MAX and NULL count for *columns*."""
    if not columns:
        return build_count_sql(table_name, where)
    exprs: list[str] = ["COUNT(*) AS cnt"]
    if len(columns) > MAX_AGG_COLUMNS:
        _log.warning("Truncating columns from %d to %d for aggregate SQL on %s",
                     len(columns), MAX_AGG_COLUMNS, table_name)
    for c in columns[:MAX_AGG_COLUMNS]:
        qc = quote_identifier(c, ds_type)
        exprs.append(f"SUM({qc}) AS {quote_identifier(c + '__sum', ds_type)}")
        exprs.append(f"AVG({qc}) AS {quote_identifier(c + '__avg', ds_type)}")
        exprs.append(f"MIN({qc}) AS {quote_identifier(c + '__min', ds_type)}")
        exprs.append(f"MAX({qc}) AS {quote_identifier(c + '__max', ds_type)}")
        exprs.append(f"SUM(CASE WHEN {qc} IS NULL THEN 1 ELSE 0 END) "
                     f"AS {quote_identifier(c + '__null', ds_type)}")
    return ("SELECT " + ",\n       ".join(exprs)
            + f"\n  FROM {quote_identifier(table_name, ds_type)}{_where_clause(where)}")


# ---------------------------------------------------------------------------
# Aggregate comparison
# ---------------------------------------------------------------------------

_METRIC_OFFSETS = {"sum": 0, "avg": 1, "min": 2, "max": 3, "null_count": 4}


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
    if len(columns) > MAX_AGG_COLUMNS:
        _log.warning("Truncating columns from %d to %d for aggregate comparison on %s / %s",
                     len(columns), MAX_AGG_COLUMNS, table_a, table_b)
    for i, col in enumerate(columns[:MAX_AGG_COLUMNS]):
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
    """Compare rows by primary key columns (matched case-insensitively)."""
    def _key_index(cols: list[str], name: str, side: str) -> int:
        try:
            return cols.index(name)
        except ValueError:
            lower_map = {c.lower(): i for i, c in enumerate(cols)}
            idx = lower_map.get(name.lower())
            if idx is None:
                raise ValueError(
                    f"Key column {name!r} not found in table {side} "
                    f"(available: {', '.join(cols)})"
                ) from None
            return idx

    key_idx_a = [_key_index(cols_a, k, "A") for k in key_cols]
    key_idx_b = [_key_index(cols_b, k, "B") for k in key_cols]

    shared = [c for c in cols_a if c in cols_b]
    key_lower = {k.lower() for k in key_cols}
    val_cols = [c for c in shared if c.lower() not in key_lower]

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

def build_profile_sql(table_name: str, columns: list[str], where: str = "",
                      ds_type: str = "") -> str:
    """Build SQL to compute distinct count, null count, min, max per column."""
    if not columns:
        return build_count_sql(table_name, where)
    exprs: list[str] = ["COUNT(*) AS cnt"]
    if len(columns) > MAX_AGG_COLUMNS:
        _log.warning("Truncating columns from %d to %d for profile SQL on %s",
                     len(columns), MAX_AGG_COLUMNS, table_name)
    for c in columns[:MAX_AGG_COLUMNS]:
        qc = quote_identifier(c, ds_type)
        exprs.append(f"COUNT(DISTINCT {qc}) AS {quote_identifier(c + '__dist', ds_type)}")
        exprs.append(f"SUM(CASE WHEN {qc} IS NULL THEN 1 ELSE 0 END) "
                     f"AS {quote_identifier(c + '__null', ds_type)}")
        exprs.append(f"MIN({qc}) AS {quote_identifier(c + '__min', ds_type)}")
        exprs.append(f"MAX({qc}) AS {quote_identifier(c + '__max', ds_type)}")
    return ("SELECT " + ",\n       ".join(exprs)
            + f"\n  FROM {quote_identifier(table_name, ds_type)}{_where_clause(where)}")


def compare_profiles(
    table_a: str, row_a: tuple, total_a: int,
    table_b: str, row_b: tuple, total_b: int,
    columns: list[str],
) -> ProfileResult:
    """Compare column profiles from SQL built by ``build_profile_sql``."""
    items: list[ProfileItem] = []
    if len(columns) > MAX_AGG_COLUMNS:
        _log.warning("Truncating columns from %d to %d for profile comparison on %s / %s",
                     len(columns), MAX_AGG_COLUMNS, table_a, table_b)
    for i, col in enumerate(columns[:MAX_AGG_COLUMNS]):
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


def parse_column_mapping(raw: str) -> ColumnMapping:
    """Parse 'col_a:col_b, name:full_name' into {col_a: col_b}.

    Pairs may be separated by commas or newlines — users pasting one
    mapping per line used to have everything after the first colon
    swallowed into a single bogus value."""
    mapping: ColumnMapping = {}
    if not raw.strip():
        return mapping
    for pair in re.split(r"[,\n]", raw):
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
    "sqlite":     "SELECT * FROM {table}{where} ORDER BY RANDOM() LIMIT {limit}",
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
# Trend data  (H)
# ---------------------------------------------------------------------------

def build_trend_data(
    reports_dir: Path,
) -> list[dict[str, Any]]:
    """Read saved reports and extract time-series delta data.

    Returns a list of dicts with keys: timestamp, table_a, table_b, delta,
    delta_pct, mismatches, schema_changes — plus, when the report carries a
    skew analysis, ``skew_top1`` / ``skew_gini`` (worst column, either side)
    and ``skew_top1_jump`` / ``skew_gini_jump`` (change vs the previous
    report with skew data, for distribution-drift alerting).
    """
    if not reports_dir.is_dir():
        return []

    entries: list[dict[str, Any]] = []

    def _file_ts(p: Path) -> str:
        # filenames are compare_[<ta>_vs_<tb>_]YYYYmmdd_HHMMSS.json — the
        # timestamp is always the trailing token, table names are optional
        m = re.search(r"(\d{8}_\d{6})$", p.stem)
        return m.group(1) if m else p.stem.replace("compare_", "")

    for fpath in sorted(reports_dir.glob("compare_*.json"), key=_file_ts):
        try:
            with open(fpath, encoding="utf-8") as f:
                d = json.load(f)
            ts = _file_ts(fpath)
            report = CompareReport.from_dict(d)
            if report.row_count:
                entry: dict[str, Any] = {
                    "timestamp": ts,
                    "table_a": report.row_count.table_a,
                    "table_b": report.row_count.table_b,
                    "delta": report.row_count.delta,
                    "delta_pct": report.row_count.delta_pct,
                    "mismatches": report.aggregate.mismatches if report.aggregate else 0,
                    "schema_changes": len(report.schema.items) if report.schema else 0,
                    "skew_top1": None,
                    "skew_gini": None,
                }
                if report.skew is not None and report.skew.items:
                    entry["skew_top1"] = max(
                        max(it.top1_pct_a, it.top1_pct_b)
                        for it in report.skew.items)
                    entry["skew_gini"] = max(
                        max(it.gini_a, it.gini_b) for it in report.skew.items)
                entries.append(entry)
        except Exception:
            _log.warning(
                "Skipping corrupt report: %s", fpath, exc_info=True)
            continue

    # Drift fields: change vs the previous report that had skew data, so a
    # rule like ``skew_top1_jump>10:1`` fires on a sudden hot-key surge.
    prev_top1: float | None = None
    prev_gini: float | None = None
    for entry in entries:
        top1, gini = entry["skew_top1"], entry["skew_gini"]
        entry["skew_top1_jump"] = (
            round(top1 - prev_top1, 2)
            if top1 is not None and prev_top1 is not None else None)
        entry["skew_gini_jump"] = (
            round(gini - prev_gini, 4)
            if gini is not None and prev_gini is not None else None)
        if top1 is not None:
            prev_top1, prev_gini = top1, gini
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
    rules: list[QualityRule], profile: ProfileResult, side: str = "a",
) -> list[QualityResult]:
    """Evaluate quality rules against profile data from one side (a|b)."""
    b = side.lower() == "b"
    results: list[QualityResult] = []
    item_map = {it.column.lower(): it for it in profile.items}

    def _num(v) -> float:
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    for rule in rules:
        item = item_map.get(rule.column.lower())
        if item is None:
            results.append(QualityResult(rule=rule, actual_value=0.0, passed=False))
            continue
        if rule.rule_type == "not_null_rate":
            actual = 100.0 - (item.null_rate_b if b else item.null_rate_a)
            results.append(QualityResult(rule=rule, actual_value=actual,
                                         passed=actual >= rule.threshold))
        elif rule.rule_type == "unique_rate":
            total = (profile.total_b if b else profile.total_a) or 1
            actual = (item.distinct_b if b else item.distinct_a) / total * 100.0
            results.append(QualityResult(rule=rule, actual_value=actual,
                                         passed=actual >= rule.threshold))
        elif rule.rule_type == "min_value":
            actual = _num(item.min_b if b else item.min_a)
            results.append(QualityResult(rule=rule, actual_value=actual,
                                         passed=actual >= rule.threshold))
        elif rule.rule_type == "max_value":
            actual = _num(item.max_b if b else item.max_a)
            results.append(QualityResult(rule=rule, actual_value=actual,
                                         passed=actual <= rule.threshold))
        elif rule.rule_type == "value_range":
            lo = _num(item.min_b if b else item.min_a)
            hi = _num(item.max_b if b else item.max_a)
            passed = (rule.min_val is None or lo >= rule.min_val) and                      (rule.max_val is None or hi <= rule.max_val)
            results.append(QualityResult(rule=rule, actual_value=lo,
                                         passed=passed))
        elif rule.rule_type == "expression":
            results.append(QualityResult(
                rule=rule, actual_value=0.0, passed=False, pending=True))
    return results


# ---------------------------------------------------------------------------
# Diff → SQL generation  (C)
# ---------------------------------------------------------------------------

def _sql_literal(value: Any, ds_type: str = "mysql") -> str:
    """Format a Python value as a SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return "NULL"
        return str(value)
    s = str(value)
    if ds_type in _BACKSLASH_ESCAPE_DIALECTS:
        s = s.replace("\\", "\\\\")
    s = s.replace("'", "''")
    return f"'{s}'"


def generate_diff_sql(
    keyed_diff: KeyedDiffResult, table_target: str,
    ds_type: str = "mysql",
) -> str:
    """Generate INSERT/UPDATE/DELETE SQL from a keyed diff result."""
    stmts: list[str] = []
    tbl = quote_identifier(table_target, ds_type)
    cols = keyed_diff.columns
    key_cols = keyed_diff.key_columns
    col_set = set(cols)

    for row in keyed_diff.added:
        col_names = ", ".join(quote_identifier(c, ds_type) for c in cols)
        values = ", ".join(_sql_literal(row[i], ds_type) if i < len(row) else "NULL"
                           for i in range(len(cols)))
        stmts.append(f"INSERT INTO {tbl} ({col_names}) VALUES ({values});")

    for row in keyed_diff.removed:
        wheres = []
        for kc in key_cols:
            if kc not in col_set:
                continue
            idx = cols.index(kc)
            wheres.append(f"{quote_identifier(kc, ds_type)} = {_sql_literal(row[idx] if idx < len(row) else None, ds_type)}")
        if wheres:
            stmts.append(f"DELETE FROM {tbl} WHERE {' AND '.join(wheres)};")

    for mod in keyed_diff.modified:
        sets = []
        for col, _old, new in mod.changes:
            sets.append(f"{quote_identifier(col, ds_type)} = {_sql_literal(new, ds_type)}")
        wheres = []
        for i, kc in enumerate(key_cols):
            wheres.append(f"{quote_identifier(kc, ds_type)} = {_sql_literal(mod.key[i], ds_type)}")
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
        return f"{local[:1] or '*'}***@{dom[:1] or '*'}***{tld}"
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

def get_upstream_tables(table_name: str, sql_list: list[str]) -> list[str]:
    from seatunnel_agent.agents.data.text2sql.lineage import trace_lineage

    seen: set[str] = set()
    target_lower = table_name.lower()
    for sql in sql_list:
        lineage = trace_lineage(sql)
        for t in lineage.source_tables:
            if t.lower() != target_lower and t.lower() not in seen:
                seen.add(t.lower())
    return sorted(seen)

# Base primitives + moved feature sections — re-exported so every existing
# import site (ui_cards, actions, chunked, tests, ...) keeps working.
from .alerts import (  # noqa: F401
    AlertRule,
    TrendAlert,
    check_trend_alerts,
    parse_alert_rules,
)
from .checksum import (  # noqa: F401
    _CUSTOM_AGG_FORBIDDEN,
    build_checksum_sql,
    build_custom_agg_sql,
    build_partition_count_sql,
    compare_checksums,
    compare_custom_aggs,
    compare_partitions,
    parse_custom_agg_expressions,
)
from .skew import (  # noqa: F401
    build_skew_sql,
    compare_skew,
    compute_skew_metrics,
    skew_side_verdict,
)
from .sync_config import (  # noqa: F401
    _escape_hocon,
    build_jdbc_url,
    generate_sync_config,
    get_jdbc_driver,
)
