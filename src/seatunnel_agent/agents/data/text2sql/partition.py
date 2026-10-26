"""Partition strategy rules for incremental/full Hive tables.

Rules (per PRD section 4 / 6.3):
- ``_di/_hi/_ri`` (incremental): user gave a time range -> convert to pt
  condition; otherwise take the table's max partition.
- ``_df/_hf`` (full): prefer the exact date partition the user mentioned;
  otherwise max partition.
- No recognizable suffix: always max partition (avoid full scans).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .schema import _FULL_SUFFIXES, _INCREMENTAL_SUFFIXES, TableSchema


def classify_table(table_name: str) -> str:
    """Return 'incremental', 'full' or 'other' from the table-name suffix."""
    lower = table_name.lower()
    if lower.endswith(_INCREMENTAL_SUFFIXES):
        return "incremental"
    if lower.endswith(_FULL_SUFFIXES):
        return "full"
    return "other"


def pt_value(d: date) -> str:
    """Format a date as the conventional yyyyMMdd partition value."""
    return d.strftime("%Y%m%d")


_DATE_PATTERNS = [
    re.compile(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?"),
    # \b fails between CJK chars and digits (both word chars), so use
    # digit lookarounds to match dates like 日期为20260312.
    re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)"),
]
_RECENT_DAYS_RE = re.compile(r"最近\s*(\d+)\s*天|past\s+(\d+)\s+days?|last\s+(\d+)\s+days?",
                             re.IGNORECASE)
_MONTH_DAY_RE = re.compile(r"(?<!\d)(\d{1,2})月(\d{1,2})日?")


@dataclass
class TimeRange:
    start: date | None = None
    end: date | None = None

    @property
    def is_empty(self) -> bool:
        return self.start is None and self.end is None


def build_partition_clause(
    table: TableSchema,
    time_range: TimeRange | None = None,
    max_partition: str | None = None,
    partition_col: str = "pt",
) -> str:
    """Return a WHERE fragment (e.g. ``pt='20260313'``) or '' if not partitioned.

    Falls back to ``max_partition`` whenever no usable time range exists —
    this guarantees partition pruning and avoids full table scans.
    """
    if not table.is_partitioned:
        return ""
    if table.partition_columns:
        partition_col = table.partition_columns[0].name

    kind = classify_table(table.name)
    tr = time_range or TimeRange()

    if kind == "incremental" and not tr.is_empty:
        if tr.start and tr.end and tr.start != tr.end:
            return (f"{partition_col} >= '{pt_value(tr.start)}' "
                    f"AND {partition_col} <= '{pt_value(tr.end)}'")
        d = tr.start or tr.end
        assert d is not None  # guarded by `not tr.is_empty`
        return f"{partition_col} = '{pt_value(d)}'"

    if kind == "full" and not tr.is_empty:
        d = tr.end or tr.start
        assert d is not None  # guarded by `not tr.is_empty`
        return f"{partition_col} = '{pt_value(d)}'"

    if max_partition:
        return f"{partition_col} = '{max_partition}'"

    # No time range and unknown max partition: caller must resolve max
    # partition first (SHOW PARTITIONS); return a marker the agent understands.
    return f"{partition_col} = '<MAX_PARTITION>'"


def has_partition_filter(sql: str, partition_col: str = "pt") -> bool:
    """Heuristic check that the SQL constrains the partition column."""
    # A trailing \b after "=" never matches (both "=" and the following
    # character are non-word), so anchor \b only on the word operators.
    pattern = re.compile(
        rf"\b{re.escape(partition_col)}\s*(=|>=|<=|>|<|(?:between|in)\b)",
        re.IGNORECASE,
    )
    return bool(pattern.search(sql))


def _parse_pt(value: str) -> date | None:
    """A partition literal as a date (yyyyMMdd / YYYY-MM-DD), else None."""
    digits = re.sub(r"\D", "", value)
    if len(digits) != 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def scan_cost_hints(
    sql: str,
    store,
    warn_partitions: int = 90,
) -> list[dict]:
    """Pre-execution scan-cost advisories for partitioned tables.

    The hard guard already rejects a MISSING partition filter; this catches
    the filters that pass it but still scan wide: a one-sided bound
    (``pt >= '2024-01-01'`` with no upper limit) and a bounded range or IN
    list covering more than *warn_partitions* daily partitions. Date-shaped
    partition values only — exotic formats produce no hint rather than a
    wrong one.
    """
    from .validator import extract_tables

    hints: list[dict] = []
    for tname in extract_tables(sql):
        table = store.get(tname)
        if table is None or not table.is_partitioned:
            continue
        name = table.partition_columns[0].name
        pcol = re.escape(name)

        eq = re.findall(rf"\b{pcol}\s*=\s*'([^']*)'", sql, re.IGNORECASE)
        in_m = re.search(rf"\b{pcol}\s+in\s*\(([^)]*)\)", sql, re.IGNORECASE)
        between = re.search(
            rf"\b{pcol}\s+between\s+'([^']*)'\s+and\s+'([^']*)'",
            sql, re.IGNORECASE,
        )
        lower = re.search(rf"\b{pcol}\s*>=?\s*'([^']*)'", sql, re.IGNORECASE)
        upper = re.search(rf"\b{pcol}\s*<=?\s*'([^']*)'", sql, re.IGNORECASE)

        if eq:
            continue  # exact partition(s) — cheapest shape
        if in_m:
            n = len([v for v in in_m.group(1).split(",") if v.strip()])
            if n > warn_partitions:
                hints.append({
                    "table": table.full_name, "partition_column": name,
                    "kind": "wide_in_list", "estimated_partitions": n,
                    "message": (
                        f"{table.full_name}: IN 列表包含 {n} 个分区值,"
                        f"超过 {warn_partitions} 的提示阈值"
                    ),
                })
            continue
        span: tuple[date, date] | None = None
        if between:
            s, e = _parse_pt(between.group(1)), _parse_pt(between.group(2))
            if s and e:
                span = (s, e)
        elif lower and upper:
            s, e = _parse_pt(lower.group(1)), _parse_pt(upper.group(1))
            if s and e:
                span = (s, e)
        elif lower or upper:
            bound = lower if lower is not None else upper
            assert bound is not None
            hints.append({
                "table": table.full_name, "partition_column": name,
                "kind": "one_sided_bound",
                "estimated_partitions": None,
                "message": (
                    f"{table.full_name}: 分区过滤只有单边界"
                    f"({name} {'>=' if lower else '<='} '{bound.group(1)}'),"
                    "另一侧不受限,可能扫描大量分区——建议补齐时间范围上下界"
                ),
            })
            continue
        if span:
            n = (span[1] - span[0]).days + 1
            if n > warn_partitions:
                hints.append({
                    "table": table.full_name, "partition_column": name,
                    "kind": "wide_range", "estimated_partitions": n,
                    "message": (
                        f"{table.full_name}: 时间范围横跨约 {n} 个分区"
                        f"({span[0].isoformat()} ~ {span[1].isoformat()}),"
                        f"超过 {warn_partitions} 的提示阈值"
                    ),
                })
    return hints
