"""并发任务冲突检测 — 多 DAG 时间线推演：超容窗、写写冲突、错峰建议.

Deterministic core: schedule each declared DAG ASAP by its own
dependencies, sweep the combined timeline for windows where slot or
memory demand exceeds the capacity, detect cross-DAG write-write
conflicts on the same table, and verify a stagger suggestion by
re-simulating with the proposed delay.  No scheduler connection.
"""

from .conflictor import (
    ConflictReport,
    Scenario,
    Window,
    compact,
    parse_scenario,
    place,
    simulate,
)
from .report import render_compact, render_markdown, render_place

__all__ = [
    "ConflictReport",
    "Scenario",
    "Window",
    "compact",
    "parse_scenario",
    "place",
    "render_compact",
    "render_markdown",
    "render_place",
    "simulate",
]
