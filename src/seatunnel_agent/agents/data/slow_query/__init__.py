"""慢查询根因分析 — 执行指标 × 历史基线 → 排序的根因与处方.

Deterministic core: parse one run's execution metrics (duration, scan
and shuffle bytes, GC/queue time, per-stage task max/median and spill),
optionally a jsonl history baseline, and rank the likely root causes —
skew, scan blow-up, spill, GC pressure, queue wait, small files — each
with evidence and a prescription pointing at the sibling agent that
fixes it.  No cluster connection.
"""

from .diagnoser import (
    Cause,
    Diagnosis,
    RunMetrics,
    StageMetrics,
    diagnose,
    parse_baseline,
    parse_metrics,
)
from .report import render_markdown

__all__ = [
    "Cause",
    "Diagnosis",
    "RunMetrics",
    "StageMetrics",
    "diagnose",
    "parse_baseline",
    "parse_metrics",
    "render_markdown",
]
