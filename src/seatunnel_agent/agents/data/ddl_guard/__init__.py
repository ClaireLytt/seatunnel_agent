"""Migration guard — grade dangerous DDL operations, generate the rollback."""

from .guard import (
    GuardFinding,
    GuardReport,
    scan_dir,
    scan_files,
    scan_sql_text,
)
from .report import render_markdown

__all__ = [
    "GuardFinding",
    "GuardReport",
    "render_markdown",
    "scan_dir",
    "scan_files",
    "scan_sql_text",
]
