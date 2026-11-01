"""实时离线核对 — 双结果集按键对齐、容差比较与系统性偏差判定.

Deterministic core: parse both result sets (sample_profile parser
reused), align rows by the declared key column(s), compare every shared
numeric column under a relative tolerance, and report missing keys,
the worst mismatches and per-metric systematic-bias verdicts (realtime
consistently lower → late data / unclosed windows; higher → duplicate
consumption).  No database connection.
"""

from .comparator import DiffResult, MetricBias, compare_results
from .report import render_markdown

__all__ = [
    "DiffResult",
    "MetricBias",
    "compare_results",
    "render_markdown",
]
