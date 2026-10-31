"""数据波动分析 — 指标时间序列 → 突增/突降/位移/走平/断档.

Deterministic core: parse date,metric,value rows (CSV or JSONL), and per
metric flag surges and drops against a rolling median + MAD window,
level shifts of the recent median vs the prior one, flatlines where a
previously moving series froze, and date gaps — ranked by severity with
the evidence numbers.  No database connection.
"""

from .analyzer import (
    VolFinding,
    VolResult,
    analyze_series,
    parse_series,
)
from .report import render_markdown

__all__ = [
    "VolFinding",
    "VolResult",
    "analyze_series",
    "parse_series",
    "render_markdown",
]
