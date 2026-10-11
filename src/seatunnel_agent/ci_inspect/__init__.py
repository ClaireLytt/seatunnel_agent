# -*- coding: utf-8 -*-
"""CI log triage — failure clustering, flaky detection, duration drift.

Deterministic, offline core; GitHub fetching is a CLI convenience."""

from .core import (
    CiReport,
    Cluster,
    analyze,
    analyze_runs,
    cluster_logs,
    collect_gh_runs,
    extract_error_lines,
    normalize_template,
    parse_runs,
)
from .report import render_markdown

__all__ = [
    "CiReport",
    "Cluster",
    "analyze",
    "analyze_runs",
    "cluster_logs",
    "collect_gh_runs",
    "extract_error_lines",
    "normalize_template",
    "parse_runs",
    "render_markdown",
]
