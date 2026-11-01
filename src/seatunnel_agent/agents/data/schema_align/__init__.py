"""源目 Schema 对齐 — 双 DDL → 按列名匹配的映射风险分级.

Deterministic core: parse both CREATE TABLE DDLs (balanced parens, so
DECIMAL(38,6) survives), match columns by name, and judge each mapping
— dropped columns, NOT NULL traps, type narrowings, risky string
conversions, temporal truncation and nullability inversions; widenings
pass silently.  No database connection.
"""

from .aligner import (
    AlignFinding,
    AlignResult,
    Column,
    align_schemas,
    parse_ddl_columns,
)
from .report import render_markdown

__all__ = [
    "AlignFinding",
    "AlignResult",
    "Column",
    "align_schemas",
    "parse_ddl_columns",
    "render_markdown",
]
