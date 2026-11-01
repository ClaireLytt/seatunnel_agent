"""测试数据生成 — 真实样例 → 保形确定性 mock 行.

Deterministic core: profile the pasted sample (sample_profile reused),
plan one strategy per column — sequences, numeric ranges, date windows,
enum distributions, null rates — and synthesize sensitive columns
(mask_preview's detectors reused) instead of sampling them, so no real
phone, ID, email or name ever reaches the output.  Same sample + seed
always generates the same rows.  No database connection.
"""

from .generator import ColumnPlan, MockResult, generate_mock
from .report import render_markdown

__all__ = [
    "ColumnPlan",
    "MockResult",
    "generate_mock",
    "render_markdown",
]
