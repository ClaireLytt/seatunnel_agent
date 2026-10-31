"""数据库运行诊断 — 状态快照 → 按严重度排序的发现与处方.

Deterministic core: parse a pasted status snapshot (JSON; every section
optional) and fire rules for connection-pool pressure, running-thread
storms, long lock waits, deadlocks, slow-query hotspots and CPU
saturation — each finding carries evidence and a prescription pointing
at the sibling agent that digs deeper.  No live database connection.
"""

from .diagnoser import (
    DbDiagnosis,
    DbFinding,
    diagnose_snapshot,
    parse_snapshot,
)
from .report import render_markdown

__all__ = [
    "DbDiagnosis",
    "DbFinding",
    "diagnose_snapshot",
    "parse_snapshot",
    "render_markdown",
]
