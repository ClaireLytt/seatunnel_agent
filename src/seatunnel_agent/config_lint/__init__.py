"""SeaTunnel config deep linter.

Param-level lint of SeaTunnel HOCON configs against the built-in connector
documentation (``connector_docs.CONNECTOR_DOCS``): unknown connectors and
parameters (with did-you-mean suggestions), missing required parameters,
value-type and enum mismatches, source/sink role violations, plus env-block
sanity (job.mode vs CDC sources, parallelism).

The existing ``validate`` tool stops at HOCON syntax + section presence;
this agent goes down to each parameter. Fully deterministic — no SeaTunnel
installation, no database, no LLM; configs are parsed, never executed.
"""

from .linter import (
    LintFinding,
    LintResult,
    lint_dir,
    lint_file,
    lint_text,
)
from .report import render_batch_markdown, render_markdown, result_to_dict

__all__ = [
    "LintFinding",
    "LintResult",
    "lint_dir",
    "lint_file",
    "lint_text",
    "render_batch_markdown",
    "render_markdown",
    "result_to_dict",
]
