# -*- coding: utf-8 -*-
"""Release-notes helper — conventional-commit changelog + semver suggestion.

Deterministic core over plain commit-log text; git access and the optional
LLM polish are CLI/UI conveniences.
"""

from .core import (
    Commit,
    ReleaseNotes,
    build_notes,
    collect_git_log,
    current_version_from_pyproject,
    next_semver,
    parse_commit_lines,
    suggest_bump,
)
from .report import polish_markdown, render_markdown

__all__ = [
    "Commit",
    "ReleaseNotes",
    "build_notes",
    "collect_git_log",
    "current_version_from_pyproject",
    "next_semver",
    "parse_commit_lines",
    "polish_markdown",
    "render_markdown",
    "suggest_bump",
]
