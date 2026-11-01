"""SQL 语义对比 — 两版取数 SQL → 分级语义差异.

Deterministic core: parse both versions (sqlglot, the lineage stack),
pair statements by write target, and report only differences that
change meaning — dropped output columns and INSERT mode flips
(breaking), expression / filter / aggregation changes and source tables
in or out (risk), new statements or columns (info).  Formatting,
aliases and ordering never count.  No database connection.
"""

from .differ import SqlDiffFinding, SqlDiffReport, diff_sql
from .report import render_markdown

__all__ = [
    "SqlDiffFinding",
    "SqlDiffReport",
    "diff_sql",
    "render_markdown",
]
