"""SQL 索引与分区推荐 — 查询模式 × 表结构 → 分区/分桶/组合索引.

Deterministic core: parse the workload with sqlglot, count per
table-column equality / range / join / GROUP BY hits, and recommend the
partition column (date-like, most-filtered), the bucketing column
(hottest join key) and a composite index (equality columns by
frequency, range column last) — each with the statements served and a
ready-to-adapt DDL fragment.  No database connection.
"""

from .advisor import (
    ColumnStats,
    TableAdvice,
    WorkloadAdvice,
    analyze_workload,
    audit,
    cold_columns,
    parse_ddl_layout,
    parse_ddl_types,
    recommend,
)
from .report import render_audit, render_cold_columns, render_markdown

__all__ = [
    "ColumnStats",
    "TableAdvice",
    "WorkloadAdvice",
    "analyze_workload",
    "audit",
    "cold_columns",
    "parse_ddl_layout",
    "parse_ddl_types",
    "recommend",
    "render_audit",
    "render_cold_columns",
    "render_markdown",
]
