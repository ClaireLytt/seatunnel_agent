"""SQL formatter / style checker.

Deterministic sqlglot pretty-printing with a black-style workflow: format
inline SQL or a directory, show a unified diff in ``--check`` mode, write
back with ``--write``, and gate CI with ``--fail-on error|change``. A
statement that does not parse is kept verbatim and reported — formatting
never destroys content.

Complements SQL Review: that agent judges semantics and performance, this
one makes every script look the same. No database, no LLM.
"""

from .formatter import (
    FmtFileResult,
    FmtResult,
    format_text,
    fmt_dir,
)
from .report import render_batch_markdown, render_markdown, result_to_dict

__all__ = [
    "FmtFileResult",
    "FmtResult",
    "format_text",
    "fmt_dir",
    "render_batch_markdown",
    "render_markdown",
    "result_to_dict",
]
