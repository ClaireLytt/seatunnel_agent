"""数据抽样剖析 — CSV/JSONL 样本 → 列剖面 + 异常发现.

Deterministic core: parse CSV (header row) or JSONL rows, take a
reproducible stride sample, profile every column (type inference,
null/unique rates, numeric range, top values, format buckets) and rank
anomaly findings — mixed types, high nulls, constant columns, outlier
formats with row numbers, numbers stored as text, whitespace/case
drift.  No database connection.
"""

from .profiler import (
    ColumnProfile,
    Finding,
    ProfileResult,
    parse_rows,
    profile_rows,
    sample_rows,
)
from .report import render_markdown

__all__ = [
    "ColumnProfile",
    "Finding",
    "ProfileResult",
    "parse_rows",
    "profile_rows",
    "render_markdown",
    "sample_rows",
]
