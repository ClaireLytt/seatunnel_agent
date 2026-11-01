"""实时延迟分析 — 事件时间戳 → 分段/端到端分位、主导段与离群事件.

Deterministic core: parse per-event timestamp rows (CSV or JSONL; the
*_ts columns define the pipeline stages, later stages may be missing),
compute per-hop and end-to-end p50/p95/max, name the dominant hop,
surface outlier events above 3x the end-to-end p95 with their worst
hop, and count SLA breaches against an optional threshold.  No
connection to anything.
"""

from .analyzer import (
    LatencyResult,
    StageStats,
    analyze_latency,
    parse_events,
)
from .report import render_markdown

__all__ = [
    "LatencyResult",
    "StageStats",
    "analyze_latency",
    "parse_events",
    "render_markdown",
]
