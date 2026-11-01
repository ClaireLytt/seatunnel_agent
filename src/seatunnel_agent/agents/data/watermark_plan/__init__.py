"""水位线选型 — 观测事件 → 实测迟到分布与乱序容忍建议.

Deterministic core: parse the events (sample_profile's parser reused),
measure the lateness distribution and the out-of-order share, and size
the bound as the regular p99 plus a margin — hour-plus stragglers are
excluded so small samples do not degrade p99 to max (the rt_latency
lesson) — emitting the Flink SQL WATERMARK clause and the
forBoundedOutOfOrderness snippet, with producer clock skew, heavy tails
and stragglers graded.  No cluster connection.
"""

from .planner import WatermarkFinding, WatermarkPlan, plan_watermark
from .report import render_markdown

__all__ = [
    "WatermarkFinding",
    "WatermarkPlan",
    "plan_watermark",
    "render_markdown",
]
