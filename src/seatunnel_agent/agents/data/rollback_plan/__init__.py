"""回滚编排 — 坏表 × 血缘 → 恢复/分层重跑/验证步骤与估时.

Deterministic core: build the lineage from the pasted SQL (quality_trace
helper reused), walk DOWNSTREAM of the bad table into topological
levels, and emit the plan — restore the table (snapshot / rerun /
overwrite templates), re-run each level (parallel inside a level),
verify every touched table — with a critical-path estimate when
per-table durations are given.  No scheduler connection.
"""

from .planner import RollbackPlan, RollbackStep, plan_rollback
from .report import render_markdown

__all__ = [
    "RollbackPlan",
    "RollbackStep",
    "plan_rollback",
    "render_markdown",
]
