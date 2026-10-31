"""数据重复检测 — 全行/主键/业务事件三层重复组 + 差异列定位来源.

Deterministic core: parse CSV (header row) or JSONL rows and detect
duplicates on three layers — identical rows, repeated primary keys and
repeated business-event keys.  Each group reports its size, first/last
row numbers and the differing columns, which locate the duplication
source (retried load, upstream fan-out, missing dedup window).  No
database connection.
"""

from .detector import DupGroup, DupResult, detect_dups
from .report import render_markdown

__all__ = [
    "DupGroup",
    "DupResult",
    "detect_dups",
    "render_markdown",
]
