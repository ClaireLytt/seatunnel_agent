"""分区健康体检 — 分区清单 → 断档/空分区/倾斜/涨缩发现.

Deterministic core: group the pasted partition listing per table and
judge the partitions themselves — date gaps in the sequence, empty
partitions, size skew against the table median, and a surging or
shrunken latest partition — each with evidence and a prescription.
No database connection.
"""

from .analyzer import (
    PartitionHealthResult,
    PartitionRow,
    PhFinding,
    analyze_partitions,
    parse_partition_listing,
)
from .report import render_markdown

__all__ = [
    "PartitionHealthResult",
    "PartitionRow",
    "PhFinding",
    "analyze_partitions",
    "parse_partition_listing",
    "render_markdown",
]
