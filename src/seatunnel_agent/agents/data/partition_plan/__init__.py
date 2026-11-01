"""分区键选型 — 数据样例 + 查询负载 → 候选键排名与 DDL 子句.

Deterministic core: profile the sample (sample_profile reused), count
WHERE-filter hits per column across the workload (sqlglot), and score
every candidate by filter share, time shape and the cardinality sweet
band — hot high-cardinality id columns get a CLUSTERED BY bucketing
suggestion instead of a partition key.  partition_health examines
partitions a table already has; this selects the key for one that has
none.  No database connection.
"""

from .planner import PartitionPlan, PlanFinding, plan_partitions
from .report import render_markdown

__all__ = [
    "PartitionPlan",
    "PlanFinding",
    "plan_partitions",
    "render_markdown",
]
