"""字段使用率 — DDL + 查询负载 → 列级引用计数与下线/裁剪候选.

Deterministic core: parse the DDL (schema_drift parser reused) and the
workload (sqlglot), resolve aliases per statement, and count every
column's references across SELECT / WHERE / JOIN / GROUP BY — tables
never read grade as offboarding candidates, never-referenced columns as
trimming candidates, SELECT * reads as blind spots.  asset_value scores
tables; this descends to the columns.  No database connection.
"""

from .analyzer import (
    FieldUsageReport,
    TableUsage,
    UsageFinding,
    analyze_usage,
)
from .report import render_markdown

__all__ = [
    "FieldUsageReport",
    "TableUsage",
    "UsageFinding",
    "analyze_usage",
    "render_markdown",
]
