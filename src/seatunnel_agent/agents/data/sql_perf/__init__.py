"""SQL 性能优化 — EXPLAIN 执行计划分析：join/shuffle/分区裁剪/下推.

Deterministic core: parse the text of ``EXPLAIN [FORMATTED]`` (Spark /
Hive) into plan facts — join types, Exchange count, per-scan
PartitionFilters / PushedFilters / column width — and turn them into
severity-ranked findings with concrete prescriptions.  Reads what the
engine planned, needs no SQL source and no engine connection.
"""

from .analyzer import (
    PerfFinding,
    PlanReport,
    ScanInfo,
    analyze,
    parse_plan,
)
from .report import render_markdown

__all__ = [
    "PerfFinding",
    "PlanReport",
    "ScanInfo",
    "analyze",
    "parse_plan",
    "render_markdown",
]
