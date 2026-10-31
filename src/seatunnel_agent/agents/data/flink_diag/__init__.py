"""Flink 作业诊断 — 作业快照 → checkpoint/背压/watermark/重启发现.

Deterministic core: parse a pasted job snapshot (JSON; every section
optional) and fire rules for checkpoint failures, duration blow-ups vs
the median, alignment-dominated checkpoints, backpressured operators,
watermark lag and restart churn — each finding carries evidence and a
prescription pointing at the sibling agent that digs deeper.  No
cluster connection.
"""

from .diagnoser import (
    FlinkDiagnosis,
    FlinkFinding,
    diagnose_job,
    parse_job_snapshot,
)
from .report import render_markdown

__all__ = [
    "FlinkDiagnosis",
    "FlinkFinding",
    "diagnose_job",
    "parse_job_snapshot",
    "render_markdown",
]
