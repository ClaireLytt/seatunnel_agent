"""事故复盘 — 事件日志 → 时间线与发现/响应/恢复用时.

Deterministic core: parse the log (sample_profile's parser reused),
normalize the timeline to minutes from the first event, and compute
MTTD / MTTA / MTTR from what was actually written down — detection lag,
response lag, mid-incident silent windows and a missing recovery event
graded.  task_failure explains why a job crashed; this reviews how the
incident was handled.  No monitoring connection.
"""

from .report import render_markdown
from .reviewer import IncidentFinding, IncidentReview, review_incident

__all__ = [
    "IncidentFinding",
    "IncidentReview",
    "render_markdown",
    "review_incident",
]
