# -*- coding: utf-8 -*-
"""Cost & resource optimization advisor (成本优化顾问).

Crosses the query audit log (``logs/text2sql_queries.jsonl``) with SQL
pattern analysis to answer "where does the compute go": Top-N expensive
query templates, per-table scan cost, queries missing partition filters,
and expensive-pattern findings (global distinct, cartesian joins, global
ORDER BY — reusing the data_skew rule engine).

Recommendations only — never touches a table, never executes SQL, no LLM.
"""

from .analyzer import analyze_cost, CostReport
from .report import render_markdown, report_to_dict

__all__ = ["analyze_cost", "CostReport", "render_markdown", "report_to_dict"]
