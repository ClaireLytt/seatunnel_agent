"""Data-contract checker — declared expectations vs actual DDL."""

from .checker import (
    ContractFinding,
    ContractReport,
    check_dir,
    check_files,
    check_sql_text,
    parse_contract,
)
from .report import render_markdown

__all__ = [
    "ContractFinding",
    "ContractReport",
    "check_dir",
    "check_files",
    "check_sql_text",
    "parse_contract",
    "render_markdown",
]
