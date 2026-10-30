"""任务重跑规划 — 失败节点 × 下游闭包 → 最小影响面的重跑批次.

Deterministic core: parse the task dependency graph (same formats as
the DAG optimizer), take the failed tasks and their downstream closure
as the minimal rerun set (upstream outputs are kept, sibling branches
untouched), flag succeeded tasks inside the closure whose inputs went
stale, and order the set into topological batches with the blast
radius.  No scheduler or database connection.
"""

from .planner import RerunPlan, RerunTask, parse_dag, plan_rerun
from .report import render_markdown

__all__ = [
    "RerunPlan",
    "RerunTask",
    "parse_dag",
    "plan_rerun",
    "render_markdown",
]
