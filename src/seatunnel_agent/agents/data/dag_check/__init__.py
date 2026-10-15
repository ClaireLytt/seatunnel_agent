"""Scheduling DAG health checker.

Builds the job dependency DAG from SQL files (and optionally SeaTunnel
configs) via the lineage graph, then reports what breaks a scheduler:
dependency cycles, mid-layer tables nobody produces (dangling upstream),
mid-layer tables nobody consumes, isolated tables — plus constructive
output: topological execution batches and the critical (longest) path.

Fully deterministic — no database, no LLM, nothing executed.
"""

from .checker import (
    DagFinding,
    DagReport,
    check_graph,
    check_sql_dir,
)
from .report import render_markdown, report_to_dict

__all__ = [
    "DagFinding",
    "DagReport",
    "check_graph",
    "check_sql_dir",
    "render_markdown",
    "report_to_dict",
]
