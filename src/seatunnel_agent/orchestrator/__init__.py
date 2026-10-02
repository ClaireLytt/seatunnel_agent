# -*- coding: utf-8 -*-
"""Agent orchestrator — one chat entry routed across the whole platform.

An LLM with one tool per deterministic agent (SQL review, transpile, impact,
migration, skew, fmt, lint, drift, PII, testgen) picks and chains tools in a
bounded loop.  Without an API key it degrades to deterministic keyword
suggestions (suggest-only, never executes).
"""

from .catalog import AgentSpec, build_catalog, tool_definitions
from .engine import Orchestrator, OrchestratorResult, Step
from .report import render_markdown
from .router import Suggestion, render_suggestions, suggest

__all__ = [
    "AgentSpec",
    "Orchestrator",
    "OrchestratorResult",
    "Step",
    "Suggestion",
    "build_catalog",
    "render_markdown",
    "render_suggestions",
    "suggest",
    "tool_definitions",
]
