"""分区补数计划器 — 缺失分区 × 血缘级联 → 拓扑有序的补数计划.

Deterministic core: reuse the freshness agent's update-event inventory
and cadence rules to find each table's missing partition slots on a
daily/hourly grid, push the gaps through the lineage's downstream
closure (downstream tables must re-run for those dates), and order the
impacted tables into topological batches. Optional command template
renders one runnable line per (table, date). No database or scheduler
connection.
"""

from .planner import (
    BackfillPlan,
    TablePlan,
    compact_ranges,
    missing_slots,
    plan,
    plan_to_dict,
)
from .report import render_markdown

__all__ = [
    "BackfillPlan",
    "TablePlan",
    "compact_ranges",
    "missing_slots",
    "plan",
    "plan_to_dict",
    "render_markdown",
]
