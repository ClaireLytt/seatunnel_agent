"""Deterministic static auto-fix for mechanical lint findings (no LLM).

Complements :mod:`fixer` (LLM rewrite): only definite, semantics-safe
patches are applied — wrong NULL comparisons, unquoted numeric partition
values, and DISTINCT that is redundant next to GROUP BY. Everything else
still needs the LLM fixer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import ReviewConfig
from .linter import clean_sql, line_of

_NULL_EQ_RE = re.compile(r"(=|!=|<>)\s*null\b", re.IGNORECASE)
_DISTINCT_RE = re.compile(r"\bselect\s+(distinct)\s+", re.IGNORECASE)
_GROUP_BY_RE = re.compile(r"\bgroup\s+by\b", re.IGNORECASE)
_SELECT_RE = re.compile(r"\bselect\b", re.IGNORECASE)


@dataclass
class AppliedFix:
    rule: str      # matching lint rule key (i18n.RULE_TEXTS_EN)
    line: int
    before: str
    after: str

    def to_dict(self) -> dict:
        return {"rule": self.rule, "line": self.line,
                "before": self.before, "after": self.after}


def apply_static_fixes(
    sql: str, dialect: str = "hive", config: ReviewConfig | None = None
) -> tuple[str, list[AppliedFix]]:
    """Apply deterministic fixes to *sql*; returns (fixed_sql, applied).

    Positions are found on the literal/comment-blanked copy (clean_sql is
    length-preserving) and edits are applied to the original text, so
    occurrences inside strings and comments are never touched.
    """
    config = config or ReviewConfig()
    cleaned = clean_sql(sql)
    # (start, end, replacement, rule) — spans refer to the original sql
    edits: list[tuple[int, int, str, str]] = []

    for m in _NULL_EQ_RE.finditer(cleaned):
        fixed = "IS NULL" if m.group(1) == "=" else "IS NOT NULL"
        edits.append((m.start(), m.end(), fixed, "null_eq"))

    for col in config.partition_cols:
        for m in re.finditer(
            rf"\b{re.escape(col)}\s*=\s*(\d{{6,8}})\b", cleaned, re.IGNORECASE
        ):
            edits.append((m.start(1), m.end(1), f"'{m.group(1)}'",
                          "partition_numeric"))

    for m in _DISTINCT_RE.finditer(cleaned):
        rest = cleaned[m.end():]
        gb = _GROUP_BY_RE.search(rest)
        sub = _SELECT_RE.search(rest)
        if gb and (not sub or gb.start() < sub.start()):
            edits.append((m.start(1), m.end(), "", "distinct_with_groupby"))

    edits.sort(key=lambda e: e[0])
    applied: list[AppliedFix] = []
    out = sql
    prev_start = len(sql) + 1
    for start, end, repl, rule in reversed(edits):
        if end > prev_start:  # overlapping edit — keep the later one only
            continue
        prev_start = start
        applied.append(AppliedFix(
            rule=rule, line=line_of(sql, start),
            before=sql[start:end].strip(), after=repl or "(removed)",
        ))
        out = out[:start] + repl + out[end:]
    applied.reverse()
    return out, applied


def describe_fixes(fixes: list[AppliedFix], lang: str = "zh") -> str:
    if lang == "en":
        return "\n".join(
            f"- Line {f.line}: `{f.before}` -> `{f.after}` [{f.rule}]"
            for f in fixes
        )
    return "\n".join(
        f"- 行 {f.line}: `{f.before}` → `{f.after}`（{f.rule}）"
        for f in fixes
    )
