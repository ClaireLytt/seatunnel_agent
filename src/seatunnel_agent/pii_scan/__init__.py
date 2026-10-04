"""PII / sensitive-column scanner.

Naming rules × column lineage: match column names and comments against a
sensitive-data rule catalog, then follow column-level lineage downstream to
report where each hit spreads and whether the propagation is masked.

Fully deterministic — no database connection, no LLM, nothing executed.
"""

from .rules import DEFAULT_RULES, MASKING_FUNCS, PiiRule, load_extra_rules
from .scanner import (
    ColumnRef,
    PiiFinding,
    PiiReport,
    SpreadEdge,
    collect_columns_from_ddl,
    scan_dir,
    scan_files,
    scan_sql_text,
)
from .report import render_markdown, report_to_dict

__all__ = [
    "DEFAULT_RULES",
    "MASKING_FUNCS",
    "PiiRule",
    "load_extra_rules",
    "ColumnRef",
    "PiiFinding",
    "PiiReport",
    "SpreadEdge",
    "collect_columns_from_ddl",
    "scan_dir",
    "scan_files",
    "scan_sql_text",
    "render_markdown",
    "report_to_dict",
]
