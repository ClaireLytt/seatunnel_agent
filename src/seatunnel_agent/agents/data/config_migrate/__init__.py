"""DataX / Sqoop → SeaTunnel config migration agent.

Deterministic, rule-based conversion with a structured issue list; no LLM,
no database connection.
"""

from .migrator import (
    BatchResult,
    Issue,
    MigrateResult,
    collect_jobs,
    migrate_datax,
    migrate_dir,
    migrate_file,
    migrate_sqoop,
    migrate_text,
)
from .report import render_batch_markdown, render_migrate_markdown

__all__ = [
    "BatchResult",
    "Issue",
    "MigrateResult",
    "collect_jobs",
    "migrate_datax",
    "migrate_dir",
    "migrate_file",
    "migrate_sqoop",
    "migrate_text",
    "render_batch_markdown",
    "render_migrate_markdown",
]
