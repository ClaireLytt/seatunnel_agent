"""Metric caliber consistency checker.

Scans a SQL tree's column-level lineage and reports output columns that
share one name but are DEFINED differently across jobs — the number-one
cause of "two reports disagree":

- **high**   — same metric name, two different computed expressions
  (``gmv = sum(amount)`` vs ``gmv = sum(amount - refund)``)
- **medium** — same name, plain copies from different source columns
  (``contact ← phone`` vs ``contact ← email``)

Expressions are canonicalized (aliases stripped, qualifiers dropped,
COUNT(1)≡COUNT(*)) before comparing, so formatting differences never
raise a conflict. Fully deterministic — no database, no LLM.
"""

from .differ import (
    MetricConflict,
    MetricDef,
    MetricReport,
    canonical_expr,
    check_graph,
    check_sql_dir,
)
from .report import render_markdown, report_to_dict

__all__ = [
    "MetricConflict",
    "MetricDef",
    "MetricReport",
    "canonical_expr",
    "check_graph",
    "check_sql_dir",
    "render_markdown",
    "report_to_dict",
]
