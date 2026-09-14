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
from datetime import date, timedelta

from .schema import TableSchema, _INCREMENTAL_SUFFIXES, _FULL_SUFFIXES


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


def extract_time_range(query: str, today: date | None = None) -> TimeRange:
    """Best-effort extraction of a date/range from the question text."""
    today = today or date.today()

    m = _RECENT_DAYS_RE.search(query)
    if m:
        days = int(next(g for g in m.groups() if g))
        return TimeRange(start=today - timedelta(days=days), end=today)

    for pattern in _DATE_PATTERNS:
        m = pattern.search(query)
        if m:
            y, mo, d = (int(g) for g in m.groups())
            try:
                found = date(y, mo, d)
            except ValueError:
                continue
            return TimeRange(start=found, end=found)

    m = _MONTH_DAY_RE.search(query)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        try:
            found = date(today.year, mo, d)
        except ValueError:
            return TimeRange()
        if found > today:
            found = found.replace(year=today.year - 1)
        return TimeRange(start=found, end=found)

    return TimeRange()


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
        return f"{partition_col} = '{pt_value(d)}'"

    if kind == "full" and not tr.is_empty:
        d = tr.end or tr.start
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
