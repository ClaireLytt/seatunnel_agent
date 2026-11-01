"""质量根因追踪 — 质量事件 × SQL 血缘 → 上游嫌疑排行 + 验证 SQL.

Deterministic core: build the lineage graph from pasted SQL scripts
(data_lineage parser reused), walk the polluted table's ancestors and
score every one as a suspect — distance decay, column-level taint bonus,
transforming-expression bonus — each with its mutation points and a
copy-ready verification SQL.  No database connection.
"""

from .report import render_markdown
from .tracer import (
    Suspect,
    TraceResult,
    build_graph_from_sql,
    trace_quality,
)

__all__ = [
    "Suspect",
    "TraceResult",
    "build_graph_from_sql",
    "render_markdown",
    "trace_quality",
]
