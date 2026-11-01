"""一致性修复 — 数据行 → 按级别排序的修复 SQL 模板清单.

Deterministic core: run the dup_check detector and the sample_profile
profiler over the pasted rows, then turn every confirmed issue into a
copy-ready repair action — ROW_NUMBER dedup, COALESCE null backfill,
TRIM/LOWER standardization, numeric cleanup casts and outlier-format
rewrites — ranked by severity with <angle-bracket> placeholders left
for human decisions.  No database connection.
"""

from .planner import RepairAction, RepairPlan, plan_repairs
from .report import render_markdown

__all__ = [
    "RepairAction",
    "RepairPlan",
    "plan_repairs",
    "render_markdown",
]
