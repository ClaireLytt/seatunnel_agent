"""Data Skew agent: syntax-level skew detection + LLM SQL rewrite.

Supports Spark SQL (Spark 3) and MaxCompute SQL (Hive accepted as a
compatible input dialect). Pure static analysis — the SQL is never
executed and no data source connection is required.
"""

from .agent import (
    DataSkewAgent,
    SkewAnalysisResult,
    static_skew_check,
    static_skew_report,
)
from .detector import detect_skew, normalize_dialect, split_statements
from .report import Severity, SkewFinding, SkewReport, render_report

__all__ = [
    "DataSkewAgent",
    "SkewAnalysisResult",
    "static_skew_check",
    "static_skew_report",
    "detect_skew",
    "normalize_dialect",
    "split_statements",
    "Severity",
    "SkewFinding",
    "SkewReport",
    "render_report",
]
