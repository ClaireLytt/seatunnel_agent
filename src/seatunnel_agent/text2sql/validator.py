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
    "grant", "revoke", "load", "msck", "export", "import",
    "analyze", "refresh",
})

_STATEMENT_LEVEL_RE = re.compile(
    r"(?:^|\s)(?:SET\s+\w+\s*=|ADD\s+(?:JAR|FILE|COLUMN|PARTITION)\b)",
    re.IGNORECASE,
)

# 逗号连接的表（FROM a, b）也必须全部提取，否则白名单可被绕过
_IDENT_PAT = r"[`\"]?\w+[`\"]?(?:\.[`\"]?\w+[`\"]?)?"
_ALIAS_STOP = (
    r"(?:join|where|on|group|order|having|limit|union|left|right|inner"
    r"|outer|full|cross|lateral|window|qualify|select)"
)
_ALIAS_PAT = rf"(?:\s+(?:as\s+)?(?!{_ALIAS_STOP}\b)\w+)?"
_TABLE_REF_RE = re.compile(
    rf"\b(?:from|join)\s+({_IDENT_PAT}{_ALIAS_PAT}"
    rf"(?:\s*,\s*{_IDENT_PAT}{_ALIAS_PAT})*)",
    re.IGNORECASE,
)

_LIMIT_RE = re.compile(
    r"\blimit\s+(\d+)(\s+offset\s+\d+)?\s*$", re.IGNORECASE,
)


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
            out.append(ch)
            i += 1
            while i < n and sql[i] != '"':
                out.append(sql[i])
                i += 1
            if i < n:
                out.append(sql[i])
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
        for ref in m.group(1).split(","):
            parts = ref.strip().split()
            if not parts:
                continue
            name = parts[0].replace("`", "").replace('"', "").lower()
            if name and name not in names:
                names.append(name)
    return names


def _extract_cte_names(cleaned: str) -> set[str]:
    """Collect CTE aliases from a WITH clause so they're not flagged as tables."""
    names: set[str] = set()
    for m in re.finditer(r"(?:\bwith|,)\s*(\w+)\s+as\s*\(", cleaned, re.IGNORECASE):
        names.add(m.group(1).lower())
    return names


def validate_sql(sql: str, store: SchemaStore | None = None) -> ValidationResult:
    """Validate that ``sql`` is a single, read-only SELECT on whitelisted tables."""
    errors: list[str] = []
    stripped = sql.strip().rstrip(";").strip()

    if not stripped:
        return ValidationResult(ok=False, errors=["Empty SQL"])

    cleaned = _strip_literals_and_comments(stripped)
    # 双引号内容可能是字符串字面量（Hive/CH 合法），关键字扫描前一并剥掉；
    # cleaned 本身保留双引号标识符，供表名提取使用
    keyword_scan = re.sub(r'"[^"\n]*"', '""', cleaned)

    if ";" in keyword_scan:
        errors.append("Multiple SQL statements are not allowed")
    first_word = cleaned.split(None, 1)[0].lower() if cleaned.split() else ""
    if first_word not in ("select", "with"):
        errors.append(f"Only SELECT queries are allowed (got '{first_word}')")

    tokens = set(re.findall(r"[a-zA-Z_]\w*", keyword_scan.lower()))
    banned = tokens & _FORBIDDEN_KEYWORDS
    if banned:
        errors.append(f"Forbidden keyword(s): {', '.join(sorted(banned))}")

    if _STATEMENT_LEVEL_RE.search(keyword_scan):
        errors.append("Forbidden statement-level keyword (SET/ADD)")

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


def _strip_trailing_comments(sql: str) -> str:
    """Drop comments/whitespace/semicolons after the last code character.

    Keeps mid-SQL comments (e.g. optimizer hints) intact; only the tail is
    trimmed so the LIMIT regex can anchor at end-of-statement.
    """
    i, n = 0, len(sql)
    last_code_end = 0
    while i < n:
        ch = sql[i]
        if ch == "'":
            i += 1
            while i < n:
                if sql[i] == "\\":
                    i += 2
                    continue
                if sql[i] == "'":
                    i += 1
                    break
                i += 1
            last_code_end = i
        elif ch == '"':
            i += 1
            while i < n and sql[i] != '"':
                i += 1
            if i < n:
                i += 1
            last_code_end = i
        elif sql.startswith("--", i):
            while i < n and sql[i] != "\n":
                i += 1
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            if not ch.isspace() and ch != ";":
                last_code_end = i + 1
            i += 1
    return sql[:last_code_end]


_TOP_RE = re.compile(r"\bSELECT\s+TOP\s+(\d+)\b", re.IGNORECASE)


def _enforce_limit_sqlserver(
    stripped: str, default_limit: int, max_limit: int,
) -> str:
    m = _TOP_RE.search(stripped)
    if m:
        current = int(m.group(1))
        if current > max_limit:
            return _TOP_RE.sub(f"SELECT TOP {max_limit}", stripped, count=1)
        return stripped
    if re.search(r"\bOFFSET\b.*\bFETCH\b", stripped, re.IGNORECASE | re.DOTALL):
        return stripped
    if re.match(r"\s*WITH\b", stripped, re.IGNORECASE):
        last_select = None
        for m in re.finditer(r"\bSELECT\b", stripped, re.IGNORECASE):
            last_select = m
        if last_select:
            pos = last_select.start()
            return stripped[:pos] + f"SELECT TOP {default_limit} " + stripped[pos + 6:]
    m = re.search(r"\bSELECT\b", stripped, re.IGNORECASE)
    if m:
        pos = m.start()
        return stripped[:pos] + f"SELECT TOP {default_limit} " + stripped[pos + 6:]
    return stripped


def _enforce_limit_standard(
    stripped: str, default_limit: int, max_limit: int,
) -> str:
    m = _LIMIT_RE.search(stripped)
    if m:
        current = int(m.group(1))
        if current > max_limit:
            offset_part = m.group(2) or ""
            return stripped[:m.start()] + f"LIMIT {max_limit}{offset_part}"
        return stripped
    return f"{stripped}\nLIMIT {default_limit}"


def enforce_limit(
    sql: str,
    default_limit: int = 1000,
    max_limit: int = 100000,
    dialect: str = "hive",
) -> str:
    """Ensure the query carries a row limit; cap existing limits at *max_limit*."""
    stripped = _strip_trailing_comments(sql).strip().rstrip(";").strip()
    if dialect == "sqlserver":
        return _enforce_limit_sqlserver(stripped, default_limit, max_limit)
    return _enforce_limit_standard(stripped, default_limit, max_limit)
