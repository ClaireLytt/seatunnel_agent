"""存储成本治理 — 清单 ± 分区明细 → 迁冷/清理/合并动作与释放量.

Deterministic core: reuse the asset_value inventory parser (plus an
optional avg_file_mb column and a partition listing) and emit ranked
governance actions — cold-tier moves for big untouched tables, drops
for date-shaped partitions past the retention window, and small-file
compaction — each with the estimated GB it frees or moves.  No database
connection.
"""

from .analyzer import (
    CostAction,
    CostResult,
    analyze_storage,
    parse_partitions,
    run_storage_analysis,
)
from .report import render_markdown

__all__ = [
    "CostAction",
    "CostResult",
    "analyze_storage",
    "parse_partitions",
    "render_markdown",
    "run_storage_analysis",
]
