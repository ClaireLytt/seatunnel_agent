"""Shared SQL text scrubbing.

One implementation of the "blank out string literals and comments,
preserving length and newlines" scan that sql_review.linter and
data_skew.detector each carried a drifted copy of.  The two call sites
genuinely differ in two ways, kept as flags so neither changes behavior:

- ``keep_hints``: optimizer hints ``/*+ ... */`` stay visible (data_skew
  reads them; sql_review blanks every block comment).
- ``keep_quote_chars``: only the literal's interior is blanked, the quote
  characters survive (data_skew's regexes anchor on them; sql_review
  blanks the whole literal, quotes included).
"""

from __future__ import annotations


def clean_sql(sql: str, *, keep_hints: bool = False,
              keep_quote_chars: bool = False) -> str:
    """Blank out string literals and comments, preserving length/newlines."""
    out = list(sql)
    i, n = 0, len(sql)

    def blank(start: int, end: int) -> None:
        for j in range(start, min(end, n)):
            if out[j] != "\n":
                out[j] = " "

    while i < n:
        ch = sql[i]
        if ch in ("'", '"'):
            quote = ch
            start = i
            i += 1
            while i < n:
                if sql[i] == "\\":
                    i += 2
                    continue
                if sql[i] == quote:
                    i += 1
                    break
                i += 1
            if keep_quote_chars:
                blank(start + 1, i - 1 if i <= n and i > start + 1 else i)
            else:
                blank(start, min(i, n))
        elif sql.startswith("--", i):
            start = i
            while i < n and sql[i] != "\n":
                i += 1
            blank(start, i)
        elif sql.startswith("/*", i):
            start = i
            end = sql.find("*/", i + 2)
            end = n if end == -1 else end + 2
            if not (keep_hints and sql.startswith("/*+", start)):
                blank(start, end)
            i = end
        else:
            i += 1
    return "".join(out)
