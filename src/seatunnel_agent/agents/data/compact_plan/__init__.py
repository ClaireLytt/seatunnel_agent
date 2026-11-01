"""小文件治理 — 文件清单 → 合并候选排名与收敛量.

Deterministic core: parse the inventory (sample_profile's parser
reused), mark partitions whose average file sits under the threshold
while holding 10+ files, rank merge candidates by the files they free
(toward a target file size), and grade 1000-file pressure points and
per-table small-file shares — with CONCATENATE / INSERT OVERWRITE
templates ready.  partition_health examines partition sizes; this
examines the file counts inside them.  No cluster connection.
"""

from .planner import CompactFinding, CompactPlan, plan_compaction
from .report import render_markdown

__all__ = [
    "CompactFinding",
    "CompactPlan",
    "plan_compaction",
    "render_markdown",
]
