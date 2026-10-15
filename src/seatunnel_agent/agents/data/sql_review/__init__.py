"""SQL Code Review agent: static analysis + LLM review -> CR report.

Supports Hive SQL, Spark SQL, Flink SQL and MaxCompute SQL dialects.
Pure static review — no query execution required; an optional database
connection enriches the review with real table schemas.
"""

from .agent import SQLReviewAgent, static_review, static_review_report
from .baseline import load_baseline, save_baseline, split_by_baseline
from .config import CustomRule, ReviewConfig, load_review_config
from .formats import results_to_json, results_to_sarif
from .lineage import extract_table_lineage
from .linter import lint_sql, split_statements
from .report import Finding, ReviewReport, Severity, TableLineage, render_report

__all__ = [
    "SQLReviewAgent",
    "static_review",
    "static_review_report",
    "lint_sql",
    "split_statements",
    "Finding",
    "ReviewReport",
    "Severity",
    "TableLineage",
    "render_report",
    "ReviewConfig",
    "CustomRule",
    "load_review_config",
    "extract_table_lineage",
    "load_baseline",
    "save_baseline",
    "split_by_baseline",
    "results_to_json",
    "results_to_sarif",
]
