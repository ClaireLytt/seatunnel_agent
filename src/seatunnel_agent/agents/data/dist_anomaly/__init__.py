"""数据分布异常检测 — 基线 vs 当前样本 → 漂移发现.

Deterministic core: build (or accept) two sample profiles and compare
them per column — schema adds/removes, mean shifts, null/unique-rate
jumps, category share drift (L1 with the biggest movers), appeared or
vanished categories and dominant-kind changes — ranked by severity.
No database connection.
"""

from .comparator import (
    DriftFinding,
    DriftResult,
    compare_profiles,
    load_profile,
)
from .report import render_markdown

__all__ = [
    "DriftFinding",
    "DriftResult",
    "compare_profiles",
    "load_profile",
    "render_markdown",
]
