"""SLA 达成看板 — 任务完成记录 → 逐任务达成率/迟到分位/连续破线.

Deterministic core: parse the records (sample_profile's parser reused),
score each task against its deadline — attainment rate vs target,
lateness p50/p90/worst over the late runs, longest and live miss
streaks — and grade below-target, live-streak and chronically-late
tasks.  schedule_advisor plans runs, task_failure explains crashes;
this measures the deadline promise.  No scheduler connection.
"""

from .board import SlaBoard, SlaFinding, TaskSla, build_board
from .report import render_markdown

__all__ = [
    "SlaBoard",
    "SlaFinding",
    "TaskSla",
    "build_board",
    "render_markdown",
]
