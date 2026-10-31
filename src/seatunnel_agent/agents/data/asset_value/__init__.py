"""资产价值评估 — 清单 → 透明打分、分层与价值×成本象限.

Deterministic core: parse the inventory (CSV or JSON rows of table,
size_gb, access_cnt_30d, last_access, downstream_cnt), score every
asset transparently — log-scaled access, downstream dependencies,
recency — tier it core/common/edge/idle, and place it in a value x cost
quadrant against the median size.  storage_cost reuses the parser.  No
database connection.
"""

from .report import render_markdown
from .valuer import (
    AssetRow,
    AssetValue,
    ValueResult,
    parse_inventory,
    value_assets,
)

__all__ = [
    "AssetRow",
    "AssetValue",
    "ValueResult",
    "parse_inventory",
    "render_markdown",
    "value_assets",
]
