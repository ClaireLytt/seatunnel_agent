"""SQL text/parsing primitives shared by the lint rules.

Regex/scanner helpers over a length-preserving cleaned copy of the SQL
(literals and comments blanked with spaces) so match offsets map back to
original line numbers.
"""

from __future__ import annotations

import re

_AGG_FUNCS = (
    "sum", "count", "avg", "min", "max", "collect_set", "collect_list",
    "group_concat", "wm_concat", "percentile", "percentile_approx",
    "stddev", "stddev_pop", "stddev_samp", "variance", "var_pop",
    "var_samp", "corr", "covar_pop", "covar_samp", "approx_count_distinct",
    "count_if", "any_value", "listagg",
)


def line_of(sql: str, offset: int) -> int:
    return sql.count("\n", 0, offset) + 1


def _split_top_level(text: str, sep: str = ",") -> list[str]:
    """Split on *sep* at paren depth 0."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return [p for p in (p.strip() for p in parts) if p]


def _depth_map(cleaned: str) -> list[int]:
    """Paren depth before each character."""
    depth_at: list[int] = []
    depth = 0
    for ch in cleaned:
        depth_at.append(depth)
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
    return depth_at


def _scope_end(cleaned: str, depth_at: list[int], start: int, depth: int) -> int:
    """Offset where the clause scope starting at *start* ends: the paren that
    closes below *depth*, or a statement-terminating ';'."""
    for j in range(start, len(cleaned)):
        if cleaned[j] == ")" and depth_at[j] == depth:
            return j
        if cleaned[j] == ";" and depth_at[j] <= depth:
            return j
    return len(cleaned)


def _find_keyword_positions(
    cleaned: str, keyword: str, depth_at: list[int]
) -> list[tuple[int, int]]:
    """Return (offset, paren_depth) for each occurrence of *keyword*."""
    pattern = re.compile(rf"\b{keyword}\b", re.IGNORECASE)
    return [(m.start(), depth_at[m.start()]) for m in pattern.finditer(cleaned)]


def _is_aggregate_expr(expr: str) -> bool:
    lowered = expr.lower()
    if re.search(r"\bover\s*\(", lowered):
        return True
    for fn in _AGG_FUNCS:
        if re.search(rf"\b{fn}\s*\(", lowered):
            return True
    return False


# words that cannot BE an alias
_ALIAS_STOPWORDS = frozenset((
    "end", "over", "asc", "desc", "from", "where", "when", "then", "else",
    "and", "or", "not", "null", "true", "false", "in", "is", "between",
    "like", "rlike", "regexp", "case", "by", "interval", "preceding",
    "following", "unbounded", "current", "row", "rows", "distinct", "all",
))

# operator-like keywords: an expression ending with one of these is
# incomplete, so the trailing word cannot be a bare alias
_EXPR_TAIL_KEYWORDS = frozenset((
    "like", "rlike", "regexp", "and", "or", "not", "in", "is", "between",
    "when", "then", "else", "from", "where", "by", "over", "case",
    "distinct", "all", "interval", "escape", "as",
))


def _split_alias(item: str) -> tuple[str, str | None]:
    """Split a select item into (expression, alias)."""
    item = item.strip()
    m = re.match(r"(.+?)\s+as\s+([`\w]+)\s*$", item, re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(2).strip("`")
    # trailing bare alias: "expr alias" — the last token is an identifier,
    # is not a keyword, and the expression before it is complete
    m = re.match(r"^(.+?)\s+(`?[a-zA-Z_]\w*`?)$", item, re.DOTALL)
    if m:
        expr, alias = m.group(1).strip(), m.group(2).strip("`")
        tail = re.search(r"(\w+)\s*$", expr)
        if (
            alias.lower() not in _ALIAS_STOPWORDS
            and not (tail and tail.group(1).lower() in _EXPR_TAIL_KEYWORDS)
            and not re.search(r"[+\-*/%=<>|&,^]\s*$", expr)
        ):
            return expr, alias
    return item, None


def _norm_expr(expr: str) -> str:
    return re.sub(r"\s+", "", expr.replace("`", "").lower())


def _bare_column(expr: str) -> str | None:
    e = expr.strip().strip("`")
    if re.fullmatch(r"[\w.]+", e):
        return e.split(".")[-1].lower()
    return None


_TABLE_REF_RE = re.compile(
    r"\b(?:from|join)\s+([`\"]?\w+[`\"]?(?:\.[`\"]?\w+[`\"]?)?)"
    r"(?:\s+(?:as\s+)?(`?\w+`?))?",
    re.IGNORECASE,
)

_NON_ALIAS_WORDS = frozenset((
    "on", "where", "join", "left", "right", "full", "inner", "cross", "outer",
    "semi", "anti", "natural", "group", "order", "union", "having", "limit",
    "using", "select", "when", "and", "or", "as", "set", "partition",
    "lateral", "values", "tablesample", "cluster", "distribute", "sort",
    "window", "qualify",
))


def _extract_table_refs(cleaned: str) -> list[tuple[int, str, str | None]]:
    """(offset, table_name, alias) for each FROM/JOIN table reference."""
    refs: list[tuple[int, str, str | None]] = []
    for m in _TABLE_REF_RE.finditer(cleaned):
        name = m.group(1).replace("`", "").replace('"', "").lower()
        alias = (m.group(2) or "").strip("`").lower() or None
        if alias in _NON_ALIAS_WORDS:
            alias = None
        refs.append((m.start(), name, alias))
    return refs


def _cte_names(cleaned: str) -> set[str]:
    return {
        m.group(1).lower()
        for m in re.finditer(r"(?:\bwith\s+|,\s*)(\w+)\s+as\s*\(", cleaned, re.IGNORECASE)
    }


_TYPE_FAMILIES = {
    "tinyint": "numeric", "smallint": "numeric", "int": "numeric",
    "integer": "numeric", "bigint": "numeric", "float": "numeric",
    "double": "numeric", "decimal": "numeric", "numeric": "numeric",
    "real": "numeric", "long": "numeric",
    "string": "string", "varchar": "string", "char": "string", "text": "string",
    "date": "datetime", "timestamp": "datetime", "datetime": "datetime",
    "boolean": "boolean", "bool": "boolean",
}


def _type_family(dtype: str) -> str | None:
    m = re.match(r"\s*(\w+)", dtype or "")
    return _TYPE_FAMILIES.get(m.group(1).lower()) if m else None
