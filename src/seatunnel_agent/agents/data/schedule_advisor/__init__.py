"""调度窗口优化 — 时长 × 依赖 → 最早时间线、关键路径与 SLA 余量.

Deterministic core: walk the declared durations and dependencies
(cycle-safe) into the earliest schedule, name the critical path into
the SLA task, compute the SLA margin and per-task slack, and locate the
peak-parallelism window with the tasks slack enough to move out of it.
No scheduler connection.
"""

from .advisor import (
    ScheduleResult,
    TaskSlot,
    advise_schedule,
    parse_plan,
)
from .report import render_markdown

__all__ = [
    "ScheduleResult",
    "TaskSlot",
    "advise_schedule",
    "parse_plan",
    "render_markdown",
]
