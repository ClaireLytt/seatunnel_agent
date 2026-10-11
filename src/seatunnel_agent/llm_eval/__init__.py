# -*- coding: utf-8 -*-
"""LLM eval harness — golden suites for the platform's LLM features.

YAML suites run against the production prompts (text2sql, sql_review) or a
raw prompt; deterministic checkers score the outputs; run history enables a
``--fail-on regression`` CI gate.  The optional LLM judge is advisory only
and never gates.
"""

from .baseline import RunLogger, compare
from .report import render_markdown
from .runner import CaseResult, SuiteResult, run_suite
from .scoring import run_check
from .suite import Case, Check, Suite, load_suite, parse_suite
from .targets import TARGETS

__all__ = [
    "Case",
    "CaseResult",
    "Check",
    "RunLogger",
    "Suite",
    "SuiteResult",
    "TARGETS",
    "compare",
    "load_suite",
    "parse_suite",
    "render_markdown",
    "run_check",
    "run_suite",
]
