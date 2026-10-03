# -*- coding: utf-8 -*-
"""Issue-triage agent — dedupe via BM25, locate via git grep, label + draft."""

from .engine import TriageResult, build_tools, load_issues, triage
from .report import render_markdown

__all__ = ["TriageResult", "build_tools", "load_issues", "render_markdown",
           "triage"]
