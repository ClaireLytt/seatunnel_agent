"""成本分摊 — 用量清单 + 单价 → 逐归属方账单与成本大头.

Deterministic core: parse the inventory (sample_profile's parser
reused), price storage and compute per owner, rank each team's top cost
drivers, and grade the unallocated share (nobody optimizes an unowned
cost) and single-owner concentration.  storage_cost prices what is
held; this decides who pays.  No billing-system connection.
"""

from .allocator import CostBill, CostFinding, OwnerBill, allocate_costs
from .report import render_markdown

__all__ = [
    "CostBill",
    "CostFinding",
    "OwnerBill",
    "allocate_costs",
    "render_markdown",
]
