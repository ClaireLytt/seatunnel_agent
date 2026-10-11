# -*- coding: utf-8 -*-
"""Prompt Lab — run one prompt across several LLM provider profiles.

Side-by-side outputs, token/latency metrics and diffs.  Experiments never
touch the process environment or the active profile, and profile secrets
never leave the process (APIs expose names only).
"""

from .report import render_diff, render_matrix_markdown
from .runner import (
    ACTIVE,
    CellResult,
    MatrixResult,
    run_matrix,
    settings_from_profile,
)
from .xlog import ExperimentLogger

__all__ = [
    "ACTIVE",
    "CellResult",
    "ExperimentLogger",
    "MatrixResult",
    "render_diff",
    "render_matrix_markdown",
    "run_matrix",
    "settings_from_profile",
]
