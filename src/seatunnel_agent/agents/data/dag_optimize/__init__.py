"""DAG 依赖优化 — 冗余串行边 × 并行批次 × 关键路径.

Deterministic core: parse a task dependency graph (JSON tasks/edges or
``a -> b`` text lines, optional per-task durations), find redundant
direct dependencies via transitive reduction, layer the DAG into
parallel waves, compute the duration-weighted critical path and the
ideal speedup, and flag single-in/single-out serial chains worth
fusing.  No scheduler or database connection.
"""

from .optimizer import (
    DagOptimizeResult,
    RedundantEdge,
    TaskGraph,
    optimize,
    parse_dag,
)
from .report import render_markdown

__all__ = [
    "DagOptimizeResult",
    "RedundantEdge",
    "TaskGraph",
    "optimize",
    "parse_dag",
    "render_markdown",
]
