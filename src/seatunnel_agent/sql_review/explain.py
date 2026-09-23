"""EXPLAIN-based verification for OLTP dialects.

When a live database connection is available, "the index may not be used"
guesses (leading-wildcard LIKE, function on a filtered column) are upgraded
to evidence: the query plan is fetched with EXPLAIN and the guess is only
reported when the plan actually shows a full table scan. Any confirmed full
scan is also reported as its own finding. Degrades to a no-op whenever the
plan cannot be fetched.
"""

from __future__ import annotations

import re
from typing import Any

from .report import Finding, Severity

# findings that guess "this predicate defeats the index"
INDEX_GUESS_KEYS = frozenset({"leading_wildcard_like", "where_func_on_column"})

# dialects whose EXPLAIN is cheap, side-effect free and parseable here
EXPLAIN_DIALECTS = frozenset({"mysql", "postgresql", "sqlite"})

_TEMPLATE_VAR_RE = re.compile(r"\$\{[^}]*\}")
_PG_SEQ_SCAN_RE = re.compile(r"\bSeq Scan on\s+(\w+)", re.IGNORECASE)
_SQLITE_SCAN_RE = re.compile(r"^\s*SCAN\s+(?:TABLE\s+)?(\w+)", re.IGNORECASE)


def supports_explain(dialect: str) -> bool:
    return dialect in EXPLAIN_DIALECTS


def explain_full_scan_tables(
    sql: str, dialect: str, executor: Any
) -> set[str] | None:
    """Run EXPLAIN on *sql*; return the lowercased table names the plan reads
    with a full scan. ``None`` means the plan could not be fetched (dialect
    unsupported, templated/multi-statement SQL, or the EXPLAIN itself failed)
    and nothing may be concluded."""
    if dialect not in EXPLAIN_DIALECTS or _TEMPLATE_VAR_RE.search(sql):
        return None
    from .linter import split_statements
    stmts = split_statements(sql)
    if len(stmts) != 1:
        return None
    stmt = stmts[0][1].rstrip().rstrip(";")
    prefix = "EXPLAIN QUERY PLAN" if dialect == "sqlite" else "EXPLAIN"
    try:
        result = executor.run(f"{prefix} {stmt}", max_rows=200)
    except Exception:
        return None

    tables: set[str] = set()
    cols = [c.lower() for c in result.columns]
    if dialect == "mysql":
        try:
            t_i, ty_i = cols.index("table"), cols.index("type")
        except ValueError:
            return None
        for row in result.rows:
            if str(row[ty_i] or "").upper() == "ALL" and row[t_i]:
                tables.add(str(row[t_i]).lower())
    elif dialect == "postgresql":
        for row in result.rows:
            m = _PG_SEQ_SCAN_RE.search(str(row[0]))
            if m:
                tables.add(m.group(1).lower())
    else:  # sqlite: EXPLAIN QUERY PLAN, detail text is the last column
        for row in result.rows:
            m = _SQLITE_SCAN_RE.match(str(row[-1]))
            if m:
                tables.add(m.group(1).lower())
    return tables


def verify_with_explain(
    findings: list[Finding], sql: str, dialect: str, executor: Any
) -> list[Finding]:
    """Filter/augment *findings* using the real query plan: index-guess
    findings are dropped when the plan uses an index, and every confirmed
    full scan becomes an ``explain_full_scan`` finding. Returns the findings
    unchanged when no plan is available."""
    scan = explain_full_scan_tables(sql, dialect, executor)
    if scan is None:
        return findings
    out = [f for f in findings if f.key not in INDEX_GUESS_KEYS or scan]
    for t in sorted(scan):
        out.append(Finding(
            severity=Severity.RISK,
            category="resource_usage",
            description=f"EXPLAIN 证实对 {t} 的全表扫描",
            location="全局",
            impact="查询未命中索引，数据量大时性能差",
            suggestion="为过滤列建立合适的索引，或改写查询以命中索引",
            key="explain_full_scan", args={"table": t},
        ))
    return out
