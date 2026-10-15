"""Batch log inspection agent: exception clustering over a log directory.

Deterministic template mining — events are extracted from log files
(ERROR/WARN lines plus full exception stacks), normalized into signatures
(root-cause exception × message template × top stack frame) and clustered,
so a 2 GB log directory collapses into "Top N distinct problems".

No database, no LLM on the core path; optional LLM advice on top.
"""

from .clusterer import (
    InspectReport,
    LogCluster,
    LogEvent,
    collect_log_files,
    scan_dir,
    scan_files,
    scan_text,
)
from .report import render_markdown, report_to_dict

__all__ = [
    "InspectReport",
    "LogCluster",
    "LogEvent",
    "collect_log_files",
    "scan_dir",
    "scan_files",
    "scan_text",
    "render_markdown",
    "report_to_dict",
]
