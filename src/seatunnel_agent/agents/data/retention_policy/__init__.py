"""生命周期建议 — 分区清单 → 逐表 TTL/归档/清理候选与释放空间.

Deterministic core: parse the inventory (sample_profile's parser
reused), take "today" from the newest date in the data (reproducible),
suggest each table's TTL as the age of the oldest partition anyone
still reads plus a 30-day grace, and list past-TTL unread partitions as
archive candidates — the never-read subset as purge candidates.
storage_cost prices what is held; this decides what to keep.  No
database connection.
"""

from .advisor import (
    RetentionFinding,
    RetentionReport,
    TableRetention,
    advise_retention,
)
from .report import render_markdown

__all__ = [
    "RetentionFinding",
    "RetentionReport",
    "TableRetention",
    "advise_retention",
    "render_markdown",
]
