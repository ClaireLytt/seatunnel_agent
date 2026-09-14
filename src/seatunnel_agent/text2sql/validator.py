"""SQL safety validation (PRD section 9 — hard requirements).

The JDBC connection has no credentials, so all protection lives here:
- SELECT-only whitelist: any write/DDL keyword is rejected.
- Single statement only (no stacked queries).
- Table whitelist: only tables registered in the SchemaStore may be queried.
- LIMIT enforcement to protect the cluster from unbounded scans.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .schema import SchemaStore

_FORBIDDEN_KEYWORDS = frozenset({
    "insert", "update", "delete", "drop", "alter", "truncate", "create",
    "grant", "revoke", "load", "msck", "set", "add", "export", "import",
    "analyze", "refresh",
})

_TABLE_REF_RE = re.compile(
    r"\b(?:from|join)\s+([`\"]?\w+[`\"]?(?:\.[`\"]?\w+[`\"]?)?)",
    re.IGNORECASE,
)

_LIMIT_RE = re.compile(r"\blimit\s+(\d+)\s*$", re.IGNORECASE)


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    column_warnings: list[str] = field(default_factory=list)


def _strip_literals_and_comments(sql: str) -> str:
    """Remove string literals and comments so keyword scanning is reliable."""
    out: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'":
            out.append("''")
            i += 1
            while i < n:
                if sql[i] == "\\":
                    i += 2
                    continue
                if sql[i] == "'":
                    i += 1
                    break
                i += 1
        elif ch == '"':
            out.append('""')
            i += 1
            while i < n and sql[i] != '"':
                i += 1
            i += 1
        elif sql.startswith("--", i):
            while i < n and sql[i] != "\n":
                i += 1
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def extract_tables(sql: str) -> list[str]:
    """Extract table names referenced after FROM/JOIN (best effort)."""
    cleaned = _strip_literals_and_comments(sql)
    names: list[str] = []
    for m in _TABLE_REF_RE.finditer(cleaned):
        name = m.group(1).replace("`", "").replace('"', "").lower()
        if name not in names:
            names.append(name)
    return names


def _extract_cte_names(cleaned: str) -> set[str]:
    """Collect CTE aliases from a WITH clause so they're not flagged as tables."""
    names: set[str] = set()
    for m in re.finditer(r"\b(?:with|,)\s*(\w+)\s+as\s*\(", cleaned, re.IGNORECASE):
        names.add(m.group(1).lower())
    return names


def validate_sql(sql: str, store: SchemaStore | None = None) -> ValidationResult:
    """Validate that ``sql`` is a single, read-only SELECT on whitelisted tables."""
    errors: list[str] = []
    stripped = sql.strip().rstrip(";").strip()

    if not stripped:
        return ValidationResult(ok=False, errors=["Empty SQL"])

    if ";" in _strip_literals_and_comments(stripped):
        errors.append("Multiple SQL statements are not allowed")

    cleaned = _strip_literals_and_comments(stripped)
    first_word = cleaned.split(None, 1)[0].lower() if cleaned.split() else ""
    if first_word not in ("select", "with"):
        errors.append(f"Only SELECT queries are allowed (got '{first_word}')")

    tokens = set(re.findall(r"[a-zA-Z_]+", cleaned.lower()))
    banned = tokens & _FORBIDDEN_KEYWORDS
    if banned:
        errors.append(f"Forbidden keyword(s): {', '.join(sorted(banned))}")

    tables = extract_tables(stripped)
    cte_names = _extract_cte_names(cleaned)
    real_tables = [t for t in tables if t not in cte_names]

    if store is not None:
        allowed = {name.lower() for name in store.table_names}
        for t in real_tables:
            if t not in allowed:
                errors.append(f"Table '{t}' is not in the schema whitelist")

    col_warnings: list[str] = []
    if store is not None and not errors:
        col_warnings = validate_columns(sql, store)

    return ValidationResult(
        ok=not errors, errors=errors, tables=real_tables,
        column_warnings=col_warnings,
    )


_WHERE_COL_RE = re.compile(
    r"\b(\w+)\s*(?:=|!=|<>|>=|<=|>|<|(?:not\s+)?in\b|(?:not\s+)?like\b|between\b|is\b)",
    re.IGNORECASE,
)

_GROUPBY_COL_RE = re.compile(
    r"\bgroup\s+by\s+([\w\s,.]+?)(?:\bhaving\b|\border\b|\blimit\b|\)|$)",
    re.IGNORECASE,
)

_ORDERBY_COL_RE = re.compile(
    r"\border\s+by\s+([\w\s,.]+?)(?:\blimit\b|\)|$)",
    re.IGNORECASE,
)

_SQL_KEYWORDS = frozenset({
    "select", "from", "where", "and", "or", "not", "in", "like",
    "between", "is", "null", "as", "on", "join", "left", "right",
    "inner", "outer", "full", "cross", "group", "by", "order", "having",
    "limit", "offset", "union", "all", "distinct", "case", "when", "then",
    "else", "end", "asc", "desc", "true", "false", "exists", "with",
    "over", "partition", "row_number", "rank", "dense_rank", "lead", "lag",
    "sum", "count", "avg", "min", "max", "coalesce", "cast", "if",
    "concat", "substring", "trim", "length", "floor", "ceil", "rand",
    "date_format", "datediff", "date_add", "date_sub", "current_date",
    "current_timestamp", "int", "bigint", "string", "double", "float",
    "decimal", "boolean", "array", "map", "struct",
})


_SELECT_BLOCK_RE = re.compile(
    r"\bselect\s+(.*?)\s+from\b",
    re.IGNORECASE | re.DOTALL,
)

_IDENT_RE = re.compile(r"\b(\w+)\b")


def _extract_column_refs(sql: str) -> set[str]:
    """Best-effort extraction of column names from SQL (excluding keywords and literals)."""
    cleaned = _strip_literals_and_comments(sql)
    candidates: set[str] = set()

    for m in _SELECT_BLOCK_RE.finditer(cleaned):
        select_body = m.group(1)
        if select_body.strip() == "*":
            continue
        for item in re.split(r",", select_body):
            item = item.strip()
            as_match = re.match(r"(.+?)\s+as\s+\w+\s*$", item, re.IGNORECASE)
            expr = as_match.group(1).strip() if as_match else item
            for ident_m in _IDENT_RE.finditer(expr):
                word = ident_m.group(1).lower()
                if word not in _SQL_KEYWORDS:
                    candidates.add(word)

    for m in _WHERE_COL_RE.finditer(cleaned):
        candidates.add(m.group(1).lower())
    for pattern in (_GROUPBY_COL_RE, _ORDERBY_COL_RE):
        for m in pattern.finditer(cleaned):
            for col in re.split(r"[,\s]+", m.group(1)):
                col = col.strip().lower()
                if col and col not in _SQL_KEYWORDS:
                    candidates.add(col)
    return {c for c in candidates if c not in _SQL_KEYWORDS and not c.isdigit()}


def validate_columns(sql: str, store: SchemaStore) -> list[str]:
    """Check that column refs in the SQL exist in at least one referenced table.

    Returns warnings (not errors) since aliased/computed columns can't be
    distinguished from real ones with regex alone.
    """
    tables_in_sql = extract_tables(sql)
    if not tables_in_sql:
        return []

    all_columns: set[str] = set()
    for tname in tables_in_sql:
        table = store.get(tname)
        if table:
            for col in table.columns + table.partition_columns:
                all_columns.add(col.name.lower())

    if not all_columns:
        return []

    refs = _extract_column_refs(sql)
    warnings: list[str] = []
    for ref in sorted(refs):
        if ref not in all_columns:
            warnings.append(f"Column '{ref}' not found in any referenced table schema")
    return warnings


def enforce_limit(sql: str, default_limit: int = 1000, max_limit: int = 100000) -> str:
    """Ensure the query carries a LIMIT; cap user limits at ``max_limit``."""
    stripped = sql.strip().rstrip(";").strip()
    m = _LIMIT_RE.search(stripped)
    if m:
        current = int(m.group(1))
        if current > max_limit:
            return _LIMIT_RE.sub(f"LIMIT {max_limit}", stripped)
        return stripped
    return f"{stripped}\nLIMIT {default_limit}"
