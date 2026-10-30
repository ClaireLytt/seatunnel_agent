"""调度依赖延迟分析 — 任务实例导出(JSON/CSV)的关键路径与 SLA 破线归因.

Deterministic core: parse one scheduling run's task instances (name,
start, end, deps), walk the dependency DAG to the target task, and
attribute the delay: for every task on the critical path, how long it
waited on dependencies vs how long it ran. No scheduler connection —
works on Airflow/DolphinScheduler exports or any equivalent dump.
"""

from .report import render_markdown, trace_to_dict
from .tracer import SlaTrace, TaskInstance, parse_instances, trace

__all__ = [
    "SlaTrace",
    "TaskInstance",
    "parse_instances",
    "render_markdown",
    "trace",
    "trace_to_dict",
]
