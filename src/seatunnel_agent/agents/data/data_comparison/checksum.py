"""Checksum / partition / custom-aggregate comparisons (F1-F3)."""

from __future__ import annotations

import re
from typing import Any

from .models import (
    ChecksumItem,
    ChecksumResult,
    CustomAggItem,
    CustomAggResult,
    PartitionCompareItem,
    PartitionResult,
)
from .sqlbase import (
    DEFAULT_CHECKSUM_SEGMENTS,
    _close_enough,
    _where_clause,
    cast_to_string,
    quote_identifier,
)

# ---------------------------------------------------------------------------
# Checksum comparison  (F1)
# ---------------------------------------------------------------------------

# Row-hash expression per dialect ({cols} = comma-joined string-cast columns).
# SQL Server needs CONVERT to get a hex string (HASHBYTES returns varbinary);
# ClickHouse is handled separately (its MD5 returns binary FixedString(16)).
_HASH_FUNC: dict[str, str] = {
    "mysql":      "MD5(CONCAT_WS(',', {cols}))",
    "postgresql": "MD5(CONCAT_WS(',', {cols}))",
    "hive":       "MD5(CONCAT_WS(',', {cols}))",
    "sparksql":   "MD5(CONCAT_WS(',', {cols}))",
    "doris":      "MD5(CONCAT_WS(',', {cols}))",
    "flinksql":   "MD5(CONCAT_WS(',', {cols}))",
    "sqlserver":  "CONVERT(VARCHAR(32), HASHBYTES('MD5', CONCAT_WS(',', {cols})), 2)",
}

# Segment-bucketing expression per dialect. Engines without a portable
# non-cryptographic hash (Flink SQL, SQLite) fall back to a single segment.
_SEG_FUNC: dict[str, str] = {
    "mysql":      "MOD(CRC32(CONCAT_WS(',', {cols})), {n})",
    "doris":      "MOD(CRC32(CONCAT_WS(',', {cols})), {n})",
    "postgresql": "MOD(ABS(HASHTEXT(CONCAT_WS(',', {cols}))), {n})",
    "hive":       "PMOD(HASH({raw_cols}), {n})",
    "sparksql":   "PMOD(HASH({raw_cols}), {n})",
    "sqlserver":  "ABS(CHECKSUM(CONCAT_WS(',', {cols}))) % {n}",
}


def build_checksum_sql(
    table_name: str, columns: list[str], ds_type: str = "mysql",
    where: str = "", segments: int = DEFAULT_CHECKSUM_SEGMENTS,
) -> str:
    """Build SQL to compute per-segment checksums for data verification."""
    segments = max(1, int(segments))
    qt = quote_identifier(table_name, ds_type)
    qcols = [quote_identifier(c, ds_type) for c in columns]
    cols_cast = ", ".join(cast_to_string(qc, ds_type) for qc in qcols)

    if ds_type == "sqlite":
        # SQLite has neither MD5 nor a hash function: single segment with a
        # length-sum fingerprint (valid SQL, same-engine comparisons only).
        concat = " || ',' || ".join(f"COALESCE(CAST({qc} AS TEXT), '')" for qc in qcols)
        return (
            f"SELECT 0 AS seg,"
            f"\n  COUNT(*) AS cnt,"
            f"\n  COALESCE(SUM(LENGTH({concat})), 0) AS seg_hash"
            f"\n  FROM {qt}{_where_clause(where)}"
        )

    if ds_type == "clickhouse":
        ts_cols = [f"toString({qc})" for qc in qcols]
        hash_expr = "hex(MD5(concat(" + ", ',', ".join(ts_cols) + ")))"
        seg_expr = f"cityHash64({', '.join(ts_cols)}) % {segments}"
    else:
        hash_expr = _HASH_FUNC.get(ds_type, _HASH_FUNC["mysql"]).format(cols=cols_cast)
        seg_tpl = _SEG_FUNC.get(ds_type)
        if seg_tpl is None:
            seg_expr = "0"
        else:
            seg_expr = seg_tpl.format(cols=cols_cast, raw_cols=", ".join(qcols),
                                      n=segments)

    if seg_expr == "0":
        return (
            f"SELECT 0 AS seg,"
            f"\n  COUNT(*) AS cnt,"
            f"\n  MIN({hash_expr}) AS seg_hash"
            f"\n  FROM {qt}{_where_clause(where)}"
        )
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
    qt = quote_identifier(table_name, ds_type)
    qp = quote_identifier(partition_col, ds_type)
    return (
        f"SELECT {cast_to_string(qp, ds_type)} AS part_val, COUNT(*) AS cnt"
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
    def _coerce(row: tuple, i: int) -> Any:
        if i >= len(row) or row[i] is None:
            return None
        try:
            return float(row[i])
        except (TypeError, ValueError):
            return row[i]

    items: list[CustomAggItem] = []
    mismatches = 0
    for i, (alias, expr) in enumerate(expressions):
        va = _coerce(row_a, i)
        vb = _coerce(row_b, i)
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


