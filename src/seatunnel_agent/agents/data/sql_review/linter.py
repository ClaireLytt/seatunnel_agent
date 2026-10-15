"""Deterministic static lint orchestration for SQL code review.

The regex/scanner rule functions live in checks.py; the SQL text/parsing
primitives in sqlparse_util.py. This module keeps the dialect tables,
statement splitting, config handling (inline disables, custom rules,
severity overrides) and the ``lint_sql`` entry point. Semantic checks that
need business context (NULL handling on joined columns, time boundaries,
skew keys) are left to the LLM layer — see prompts.py.
"""

from __future__ import annotations

import re
from typing import Any

from seatunnel_agent.common.sql_text import clean_sql as _clean_sql_text

from .checks import (
    _CONFIG_RULES,
    _DIALECT_RULES,
    _RULES,
    _check_join_key_types,
    _check_schema_refs,
)
from .config import DEFAULT_CONFIG, ReviewConfig
from .report import Finding, Severity
from .sqlparse_util import (  # noqa: F401 — re-exported for external users
    _cte_names,
    _depth_map,
    _extract_table_refs,
    line_of,
)

DIALECTS = (
    "hive", "spark", "flink", "maxcompute",
    "mysql", "postgresql", "sqlserver", "clickhouse", "doris", "sqlite",
)

_DIALECT_ALIASES = {
    "odps": "maxcompute",
    "sparksql": "spark",
    "flinksql": "flink",
    "hivesql": "hive",
    "postgres": "postgresql",
    "pg": "postgresql",
    "mssql": "sqlserver",
    "tsql": "sqlserver",
    "ck": "clickhouse",
}

# text2sql executor ds_type for each review dialect (None = no executor;
# callers fall back to hive for schema introspection)
EXECUTOR_DS_TYPES: dict[str, str | None] = {
    "hive": "hive", "spark": "sparksql", "flink": "flinksql",
    "maxcompute": None, "mysql": "mysql", "postgresql": "postgresql",
    "sqlserver": "sqlserver", "clickhouse": "clickhouse",
    "doris": "doris", "sqlite": "sqlite",
}


def normalize_dialect(dialect: str) -> str:
    d = (dialect or "hive").strip().lower().replace(" ", "")
    d = _DIALECT_ALIASES.get(d, d)
    return d if d in DIALECTS else "hive"


def is_known_dialect(dialect: str) -> bool:
    d = (dialect or "").strip().lower().replace(" ", "")
    return d in DIALECTS or d in _DIALECT_ALIASES


def clean_sql(sql: str) -> str:
    """Blank out string literals and comments, preserving length and newlines."""
    return _clean_sql_text(sql)


def split_statements(sql: str) -> list[tuple[int, str]]:
    """Split a script on top-level ``;`` into ``(line_offset, statement)`` pairs.

    Line offsets are 0-based deltas to add to per-statement line numbers so
    they map back to the original script. Blank segments are dropped.
    """
    cleaned = clean_sql(sql)
    depth_at = _depth_map(cleaned)
    parts: list[tuple[int, str]] = []
    prev = 0
    for i, ch in enumerate(cleaned):
        if ch == ";" and depth_at[i] == 0:
            seg = sql[prev:i + 1]
            if seg.strip().strip(";"):
                parts.append((sql.count("\n", 0, prev), seg))
            prev = i + 1
    tail = sql[prev:]
    if tail.strip():
        parts.append((sql.count("\n", 0, prev), tail))
    return parts or [(0, sql)]


_LINE_LOC_RE = re.compile(r"行 (\d+)")


def _shift_finding_lines(findings: list[Finding], delta: int) -> None:
    if not delta:
        return
    for f in findings:
        f.location = _LINE_LOC_RE.sub(
            lambda m: f"行 {int(m.group(1)) + delta}", f.location)


def _run_custom_rules(sql: str, config: ReviewConfig) -> list[Finding]:
    findings: list[Finding] = []
    for rule in config.custom_rules:
        # per-rule match cap guards against pathological patterns
        for i, m in enumerate(rule.compiled.finditer(sql)):
            if i >= config.max_custom_matches:
                break
            findings.append(Finding(
                severity=rule.severity,
                category=rule.category,
                description=rule.message,
                location=f"行 {line_of(sql, m.start())}",
                impact="命中项目自定义规则",
                suggestion=rule.suggestion or "按团队规范修改",
                source="custom",
            ))
    return findings


_DISABLE_RE = re.compile(
    r"--\s*sqlreview-disable(?P<scope>-file|-next-line)?"
    r"[ \t]*(?::[ \t]*(?P<cats>[\w]+(?:[ \t]*,[ \t]*[\w]+)*))?",
    re.IGNORECASE,
)


def _line_comment_spans(sql: str) -> list[tuple[int, int]]:
    """Spans of ``--`` line comments, skipping string literals (mirrors clean_sql)."""
    spans: list[tuple[int, int]] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'" or ch == '"':
            quote = ch
            i += 1
            while i < n:
                if sql[i] == "\\":
                    i += 2
                    continue
                if sql[i] == quote:
                    i += 1
                    break
                i += 1
        elif sql.startswith("--", i):
            start = i
            while i < n and sql[i] != "\n":
                i += 1
            spans.append((start, i))
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            i += 1
    return spans


def _parse_cats(raw: str | None) -> set[str]:
    if not raw:
        return {"*"}
    cats = {c.strip().lower() for c in raw.split(",") if c.strip()}
    return cats or {"*"}


def _apply_inline_disables(sql: str, findings: list[Finding]) -> list[Finding]:
    """Honour ``-- sqlreview-disable[-next-line|-file][: cat1, cat2]`` comments.

    Directives are only recognized inside real ``--`` line comments; the same
    text inside a string literal or block comment is ignored.
    """
    if "sqlreview-disable" not in sql.lower():
        return findings
    file_cats: set[str] = set()
    line_cats: dict[int, set[str]] = {}
    for start, end in _line_comment_spans(sql):
        m = _DISABLE_RE.search(sql, start, end)
        if not m:
            continue
        scope = (m.group("scope") or "").lower()
        cats = _parse_cats(m.group("cats"))
        line = line_of(sql, start)
        if scope == "-file":
            file_cats |= cats
        elif scope == "-next-line":
            line_cats.setdefault(line + 1, set()).update(cats)
        else:
            line_cats.setdefault(line, set()).update(cats)

    def suppressed(f: Finding) -> bool:
        def hit(cats: set[str]) -> bool:
            return "*" in cats or f.category in cats
        if file_cats and hit(file_cats):
            return True
        lm = _LINE_LOC_RE.search(f.location)
        if lm:
            cats = line_cats.get(int(lm.group(1)))
            if cats and hit(cats):
                return True
        return False

    return [f for f in findings if not suppressed(f)]


def _lint_statement(
    sql: str, dialect: str, store: Any, config: ReviewConfig,
) -> list[Finding]:
    cleaned = clean_sql(sql)
    depth_at = _depth_map(cleaned)
    findings: list[Finding] = []
    for rule in _RULES:
        findings.extend(rule(sql, cleaned, depth_at))
    for rule in _CONFIG_RULES:
        findings.extend(rule(sql, cleaned, depth_at, config))
    for rule in _DIALECT_RULES:
        findings.extend(rule(sql, cleaned, depth_at, dialect, config))
    findings.extend(_check_join_key_types(sql, cleaned, depth_at, store))
    findings.extend(_check_schema_refs(sql, cleaned, depth_at, store, config))
    return findings


def lint_sql(
    sql: str,
    dialect: str = "hive",
    store: Any = None,
    config: ReviewConfig | None = None,
) -> list[Finding]:
    """Run all deterministic rules; returns findings sorted by severity then line.

    Multi-statement scripts are split on top-level ``;`` and each statement
    is linted independently, with line numbers mapped back to the script.
    *store* (optional SchemaStore) enables schema-aware rules such as JOIN
    key type consistency. *config* (optional ReviewConfig) customizes
    partition columns, incremental suffixes, disabled rules, severities,
    and project-specific regex rules.
    """
    dialect = normalize_dialect(dialect)
    config = config or DEFAULT_CONFIG
    findings: list[Finding] = []
    from .ast_check import check_syntax
    findings.extend(check_syntax(sql, dialect))
    for offset, stmt in split_statements(sql):
        stmt_findings = _lint_statement(stmt, dialect, store, config)
        _shift_finding_lines(stmt_findings, offset)
        findings.extend(stmt_findings)

    # disable/severity config applies to built-in rules only: a custom rule
    # carries its own explicit severity and must not be silently swallowed
    # by a category-wide `disable` entry.
    if config.disabled_categories:
        findings = [f for f in findings if f.category not in config.disabled_categories]
    for f in findings:
        override = config.severity_overrides.get(f.category)
        if override is not None:
            f.severity = override
    findings.extend(_run_custom_rules(sql, config))
    findings = _apply_inline_disables(sql, findings)

    order = {Severity.CRITICAL: 0, Severity.RISK: 1, Severity.SUGGESTION: 2}

    def sort_key(f: Finding) -> tuple[int, int]:
        m = re.search(r"\d+", f.location)
        return (order[f.severity], int(m.group()) if m else 10**6)

    findings.sort(key=sort_key)
    return findings
