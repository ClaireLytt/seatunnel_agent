"""SQL 资源消耗预测 — SQL × 表统计 → 扫描/shuffle/内存/核时的代价卡.

Deterministic core: parse the SQL with sqlglot, apply partition- and
column-pruning discounts from the declared table stats, model join
shuffles (broadcast below the threshold) and aggregation exchanges,
and emit an order-of-magnitude cost card — scan bytes, shuffle bytes,
output rows, peak task memory, core-seconds, suggested parallelism and
a 0.5x–2x wall-clock band — with every assumption printed.  Tables
missing from the inventory are reported, never guessed.
"""

from .estimator import (
    CostCard,
    ScanEstimate,
    TableStats,
    compare,
    estimate,
    parse_assumptions,
    parse_stats,
    what_if,
)
from .report import render_compare, render_markdown, render_what_if

__all__ = [
    "CostCard",
    "ScanEstimate",
    "TableStats",
    "compare",
    "estimate",
    "parse_assumptions",
    "parse_stats",
    "render_compare",
    "render_markdown",
    "render_what_if",
    "what_if",
]
