"""指标异动归因 — 双结果集 × 维度 → 逐值精确可加贡献分解.

Deterministic core: parse both sliced result sets (sample_profile
parser reused), sum the metric per dimension value on each side, and
decompose the total change exactly into per-value contributions —
appeared and vanished values included — with verdicts for the top
contributor, single-value concentration and offsetting mix shifts.
No database connection.
"""

from .attributor import (
    AttributionResult,
    DimBreakdown,
    MaFinding,
    attribute_change,
)
from .report import render_markdown

__all__ = [
    "AttributionResult",
    "DimBreakdown",
    "MaFinding",
    "attribute_change",
    "render_markdown",
]
