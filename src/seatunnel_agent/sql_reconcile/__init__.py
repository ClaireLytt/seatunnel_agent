# -*- coding: utf-8 -*-
"""SQL caliber reconciliation agent (口径对账).

Two SQL statements that "should" produce the same number often don't —
because one filters ``status='paid'`` and the other doesn't, one joins
LEFT and the other INNER, one dedups by ``row_number()`` and the other by
``DISTINCT``. This module diffs two SQL trees at the AST level (sqlglot)
and reports *why* the numbers differ, by caliber category.

Deterministic — no LLM, no database, nothing executed.
"""

from .reconciler import reconcile_sql, ReconcileReport, Finding
from .report import render_markdown, report_to_dict

__all__ = [
    "reconcile_sql",
    "ReconcileReport",
    "Finding",
    "render_markdown",
    "report_to_dict",
]
