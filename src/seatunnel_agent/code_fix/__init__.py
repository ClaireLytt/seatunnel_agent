# -*- coding: utf-8 -*-
"""Code-fix agent — run tests, read, patch, re-run, until green.

A true agent: the pytest output is the environment feedback that drives
every next decision. Default isolation is a fresh git worktree; success is
verified by a deterministic final run; nothing is ever committed."""

from .engine import CodeFixResult, fix
from .report import render_markdown
from .tools import build_tools, run_pytest

__all__ = ["CodeFixResult", "build_tools", "fix", "render_markdown",
           "run_pytest"]
