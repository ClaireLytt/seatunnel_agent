"""Regex-based SQL formatter — keyword uppercasing and clause indentation."""

from __future__ import annotations

import re

_MAJOR_CLAUSES = (
    "SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY",
    "HAVING", "LIMIT", "OFFSET", "UNION ALL", "UNION",
)

_JOIN_KEYWORDS = (
    "LEFT OUTER JOIN", "RIGHT OUTER JOIN", "FULL OUTER JOIN",
    "CROSS JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN",
    "FULL JOIN", "JOIN",
)

_ALL_KEYWORDS = frozenset({
    "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "LIKE",
    "BETWEEN", "IS", "NULL", "AS", "ON", "JOIN", "LEFT", "RIGHT",
    "INNER", "OUTER", "FULL", "CROSS", "GROUP", "BY", "ORDER",
    "HAVING", "LIMIT", "OFFSET", "UNION", "ALL", "DISTINCT",
    "CASE", "WHEN", "THEN", "ELSE", "END", "EXISTS", "WITH",
    "OVER", "PARTITION", "ASC", "DESC", "SET", "INTO", "VALUES",
    "TOP", "FETCH", "NEXT", "ROWS", "ONLY", "FIRST",
    "SUM", "COUNT", "AVG", "MIN", "MAX", "COALESCE", "CAST",
    "IF", "CONCAT", "SUBSTRING", "TRIM", "LENGTH",
})

_PLACEHOLDER = "\x00STR{}\x00"
_PLACEHOLDER_RE = re.compile(r"\x00STR(\d+)\x00")


def _extract_strings(sql: str) -> tuple[str, list[str]]:
    """Replace string literals with placeholders to protect them from transformation."""
    literals: list[str] = []
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'":
            start = i
            i += 1
            while i < n:
                if sql[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            literals.append(sql[start:i])
            out.append(_PLACEHOLDER.format(len(literals) - 1))
        elif sql.startswith("--", i):
            end = sql.find("\n", i)
            if end == -1:
                end = n
            literals.append(sql[i:end])
            out.append(_PLACEHOLDER.format(len(literals) - 1))
            i = end
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            if end == -1:
                end = n
            else:
                end += 2
            literals.append(sql[i:end])
            out.append(_PLACEHOLDER.format(len(literals) - 1))
            i = end
        else:
            out.append(ch)
            i += 1
    return "".join(out), literals


def _restore_strings(sql: str, literals: list[str]) -> str:
    def _repl(m: re.Match) -> str:
        idx = int(m.group(1))
        return literals[idx] if idx < len(literals) else m.group(0)
    return _PLACEHOLDER_RE.sub(_repl, sql)


def _uppercase_keywords(sql: str) -> str:
    def _repl(m: re.Match) -> str:
        word = m.group(0)
        if word.upper() in _ALL_KEYWORDS:
            return word.upper()
        return word
    return re.sub(r"\b[a-zA-Z_]\w*\b", _repl, sql)


def format_sql(sql: str) -> str:
    """Format SQL with keyword uppercasing and clause-level line breaks."""
    if not sql or not sql.strip():
        return sql

    protected, literals = _extract_strings(sql.strip())
    protected = _uppercase_keywords(protected)
    protected = re.sub(r"\s+", " ", protected).strip()

    for kw in _JOIN_KEYWORDS:
        pattern = r"\b" + r"\s+".join(kw.split()) + r"\b"
        protected = re.sub(pattern, f"\n{kw}", protected, flags=re.IGNORECASE)

    for clause in _MAJOR_CLAUSES:
        parts = clause.split()
        if len(parts) == 2:
            pattern = r"\b" + parts[0] + r"\s+" + parts[1] + r"\b"
        else:
            pattern = r"\b" + clause + r"\b"
        protected = re.sub(pattern, f"\n{clause}", protected, flags=re.IGNORECASE)

    protected = re.sub(r"\bAND\b", "\n  AND", protected, flags=re.IGNORECASE)
    protected = re.sub(r"\bOR\b", "\n  OR", protected, flags=re.IGNORECASE)

    lines = protected.split("\n")
    formatted: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            formatted.append(stripped)

    result = "\n".join(formatted)
    result = _restore_strings(result, literals)
    return result
