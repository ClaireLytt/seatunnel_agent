"""Deterministic static lint rules for SQL code review.

Regex/scanner based (no external SQL parser): each rule is best-effort and
biased toward high-precision findings. Semantic checks that need business
context (NULL handling on joined columns, time boundaries, skew keys) are
left to the LLM layer — see prompts.py.

All rules operate on a length-preserving cleaned copy of the SQL (literals
and comments blanked with spaces) so match offsets map back to original
line numbers.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from .config import DEFAULT_CONFIG, ReviewConfig
from .report import Finding, Severity

DIALECTS = (
    "hive", "spark", "flink", "maxcompute",
    "mysql", "postgresql", "sqlserver", "clickhouse", "doris", "sqlite",
)

# Engine families — rules gate on these instead of listing dialects inline.
# BATCH_WAREHOUSES: partitioned batch engines where partition pruning /
# INSERT OVERWRITE PARTITION semantics apply. OLTP: row stores where index
# usage matters and global ORDER BY is normal.
BATCH_WAREHOUSES = frozenset({"hive", "spark", "maxcompute"})
OLTP = frozenset({"mysql", "postgresql", "sqlserver", "sqlite"})
OLAP_MPP = frozenset({"clickhouse", "doris"})

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

_AGG_FUNCS = (
    "sum", "count", "avg", "min", "max", "collect_set", "collect_list",
    "group_concat", "wm_concat", "percentile", "percentile_approx",
    "stddev", "stddev_pop", "stddev_samp", "variance", "var_pop",
    "var_samp", "corr", "covar_pop", "covar_samp", "approx_count_distinct",
    "count_if", "any_value", "listagg",
)

_CLAUSE_KEYWORDS_RE = re.compile(
    r"\b(having|order\s+by|limit|window|union|cluster\s+by|distribute\s+by|sort\s+by|qualify)\b",
    re.IGNORECASE,
)


def normalize_dialect(dialect: str) -> str:
    d = (dialect or "hive").strip().lower().replace(" ", "")
    d = _DIALECT_ALIASES.get(d, d)
    return d if d in DIALECTS else "hive"


def is_known_dialect(dialect: str) -> bool:
    d = (dialect or "").strip().lower().replace(" ", "")
    return d in DIALECTS or d in _DIALECT_ALIASES


def clean_sql(sql: str) -> str:
    """Blank out string literals and comments, preserving length and newlines."""
    out = list(sql)
    i, n = 0, len(sql)

    def blank(start: int, end: int) -> None:
        for j in range(start, end):
            if out[j] != "\n":
                out[j] = " "

    while i < n:
        ch = sql[i]
        if ch == "'" or ch == '"':
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
            blank(start, min(i, n))
        elif sql.startswith("--", i):
            start = i
            while i < n and sql[i] != "\n":
                i += 1
            blank(start, i)
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            end = n if end == -1 else end + 2
            blank(i, end)
            i = end
        else:
            i += 1
    return "".join(out)


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


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def _check_groupby_completeness(
    sql: str, cleaned: str, depth_at: list[int]
) -> list[Finding]:
    findings: list[Finding] = []
    select_positions = _find_keyword_positions(cleaned, "select", depth_at)
    groupby_re = re.compile(r"\bgroup\s+by\b", re.IGNORECASE)

    for gm in groupby_re.finditer(cleaned):
        g_off = gm.start()
        g_depth = depth_at[g_off]

        # nearest preceding SELECT at the same depth
        sel_off = None
        for off, d in select_positions:
            if off < g_off and d == g_depth:
                sel_off = off
        if sel_off is None:
            continue

        from_m = None
        for fm in re.finditer(r"\bfrom\b", cleaned[sel_off:g_off], re.IGNORECASE):
            if depth_at[sel_off + fm.start()] == g_depth:
                from_m = fm
                break
        if from_m is None:
            continue
        select_body = cleaned[sel_off + 6: sel_off + from_m.start()]
        select_body = re.sub(
            r"^\s*(?:distinct|all)\b", "", select_body, count=1, flags=re.IGNORECASE
        )

        # group-by list: up to next clause keyword at same depth or closing paren
        g_end = len(cleaned)
        for cm in _CLAUSE_KEYWORDS_RE.finditer(cleaned, gm.end()):
            if depth_at[cm.start()] == g_depth:
                g_end = cm.start()
                break
        for j in range(gm.end(), g_end):
            if cleaned[j] == ")" and depth_at[j] == g_depth:
                g_end = j
                break
            if cleaned[j] == ";":
                g_end = j
                break
        group_body = cleaned[gm.end(): g_end]

        # GROUPING SETS / CUBE / ROLLUP need a real parser — skip.
        if re.search(
            r"\b(grouping\s+sets|cube|rollup)\b", group_body, re.IGNORECASE
        ):
            continue

        raw_group_items = _split_top_level(group_body)
        group_cols = {_norm_expr(it) for it in raw_group_items}
        group_bare = {b for it in raw_group_items if (b := _bare_column(it))}
        # positional GROUP BY (GROUP BY 1, 2)
        positional = all(re.fullmatch(r"\d+", it) for it in raw_group_items) and raw_group_items
        if positional:
            continue

        select_items = _split_top_level(select_body)
        missing: list[str] = []
        for item in select_items:
            if item.strip() == "*" or item.strip().endswith(".*"):
                continue
            if _is_aggregate_expr(item):
                continue
            expr, alias = _split_alias(item)
            if re.fullmatch(r"[\d.]+", expr.strip()):
                continue
            if _norm_expr(expr) in group_cols:
                continue
            # Spark/MaxCompute allow grouping by the select alias
            if alias and alias.lower() in group_bare:
                continue
            col = _bare_column(expr)
            if col and col in group_bare:
                continue
            missing.append(expr.strip())

        if missing:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                category="groupby_completeness",
                description=f"GROUP BY 缺少 {', '.join(missing)}",
                location=f"行 {line_of(sql, gm.start())}",
                impact="数据错误",
                suggestion="GROUP BY 应包含所有非聚合字段",
            ))
    return findings


_JOIN_RE = re.compile(
    r"\b(?:(left|right|full|inner|cross)\s+(?:outer\s+)?)?join\b",
    re.IGNORECASE,
)


def _check_joins(sql: str, cleaned: str, depth_at: list[int]) -> list[Finding]:
    findings: list[Finding] = []
    boundary_re = re.compile(
        r"\b(join|where|group\s+by|order\s+by|having|limit|union|on|using)\b",
        re.IGNORECASE,
    )

    def next_boundary(start: int, end: int, depth: int) -> re.Match[str] | None:
        for bm in boundary_re.finditer(cleaned, start, end):
            if depth_at[bm.start()] == depth:
                return bm
        return None

    for m in _JOIN_RE.finditer(cleaned):
        join_type = (m.group(1) or "").lower()
        line = line_of(sql, m.start())
        if join_type == "cross":
            findings.append(Finding(
                severity=Severity.RISK,
                category="join_cartesian",
                description="使用了 CROSS JOIN（笛卡尔积）",
                location=f"行 {line}",
                impact="数据量爆炸",
                suggestion="确认是否确实需要笛卡尔积，否则改为带 ON 条件的 JOIN",
            ))
            continue

        j_depth = depth_at[m.start()]
        s_end = _scope_end(cleaned, depth_at, m.end(), j_depth)
        nxt = next_boundary(m.end(), s_end, j_depth)
        has_on = nxt is not None and nxt.group(1).lower() in ("on", "using")
        if not has_on:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                category="join_cartesian",
                description="JOIN 缺少 ON 关联条件（笛卡尔积）",
                location=f"行 {line}",
                impact="数据量爆炸/结果错误",
                suggestion="为 JOIN 添加正确的 ON 关联条件",
            ))
            continue

        if nxt.group(1).lower() == "on":
            on_end = s_end
            b2 = next_boundary(nxt.end(), s_end, j_depth)
            if b2:
                on_end = b2.start()
            on_body = cleaned[nxt.end(): on_end]
            if re.search(r"\bor\b", on_body, re.IGNORECASE):
                findings.append(Finding(
                    severity=Severity.RISK,
                    category="join_condition",
                    description="JOIN 的 ON 条件中包含 OR",
                    location=f"行 {line_of(sql, nxt.start())}",
                    impact="可能产生多对多放大且无法走高效 JOIN",
                    suggestion="拆分为 UNION ALL 或改写关联逻辑",
                ))
            has_equality = bool(re.search(r"(?<![<>!])=(?!=)", on_body))
            has_range = bool(re.search(r"[<>]", on_body))
            if has_range and not has_equality:
                findings.append(Finding(
                    severity=Severity.RISK,
                    category="join_condition",
                    description="JOIN 使用非等值关联条件",
                    location=f"行 {line_of(sql, nxt.start())}",
                    impact="可能产生多对多关联放大",
                    suggestion="确认关联键，尽量使用等值 JOIN",
                ))
    return findings


_TYPE_FAMILIES = {
    "tinyint": "numeric", "smallint": "numeric", "int": "numeric",
    "integer": "numeric", "bigint": "numeric", "float": "numeric",
    "double": "numeric", "decimal": "numeric", "numeric": "numeric",
    "real": "numeric", "long": "numeric",
    "string": "string", "varchar": "string", "char": "string", "text": "string",
    "date": "datetime", "timestamp": "datetime", "datetime": "datetime",
    "boolean": "boolean", "bool": "boolean",
}

_EQ_PAIR_RE = re.compile(
    r"(`?\w+`?)\s*\.\s*(`?\w+`?)\s*=\s*(`?\w+`?)\s*\.\s*(`?\w+`?)"
)


def _type_family(dtype: str) -> str | None:
    m = re.match(r"\s*(\w+)", dtype or "")
    return _TYPE_FAMILIES.get(m.group(1).lower()) if m else None


def _check_join_key_types(
    sql: str, cleaned: str, depth_at: list[int], store: Any
) -> list[Finding]:
    """Schema-aware: flag equality comparisons whose column type families differ
    (e.g. string = bigint). Only runs when a SchemaStore is available."""
    if store is None or len(store) == 0:
        return []
    ctes = _cte_names(cleaned)
    resolve: dict[str, Any] = {}
    for _off, name, alias in _extract_table_refs(cleaned):
        if name in ctes:
            continue
        table = store.get(name)
        base = name.split(".")[-1]
        if table is None:
            table = next(
                (t for t in store.tables if t.name.lower() == base), None
            )
        if table is None:
            continue
        for key in (alias, base, name):
            if key:
                resolve.setdefault(key, table)

    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for m in _EQ_PAIR_RE.finditer(cleaned):
        lq, lc, rq, rc = (g.strip("`").lower() for g in m.groups())
        lt, rt = resolve.get(lq), resolve.get(rq)
        if lt is None or rt is None:
            continue
        lcol, rcol = lt.find_column(lc), rt.find_column(rc)
        if lcol is None or rcol is None:
            continue
        lf, rf = _type_family(lcol.dtype), _type_family(rcol.dtype)
        if not lf or not rf or lf == rf:
            continue
        key = tuple(sorted((f"{lq}.{lc}", f"{rq}.{rc}")))
        if key in seen:
            continue
        seen.add(key)
        findings.append(Finding(
            severity=Severity.RISK,
            category="join_condition",
            description=(
                f"关联键类型不一致: {lq}.{lc} ({lcol.dtype}) = "
                f"{rq}.{rc} ({rcol.dtype})"
            ),
            location=f"行 {line_of(sql, m.start())}",
            impact="隐式类型转换可能导致关联不上、结果错误或数据倾斜",
            suggestion="用 CAST 显式统一两侧类型后再关联",
        ))
    return findings


_FROM_BODY_BOUNDARY_RE = re.compile(
    r"\b(where|group\s+by|order\s+by|having|limit|union|join|left|right|full"
    r"|inner|cross|lateral|window|qualify|select)\b",
    re.IGNORECASE,
)

_TABLE_ITEM_RE = re.compile(
    r"^[`\"]?\w+[`\"]?(?:\.[`\"]?\w+[`\"]?)?(?:\s+(?:as\s+)?`?\w+`?)?$",
    re.IGNORECASE,
)


def _check_comma_join(sql: str, cleaned: str, depth_at: list[int]) -> list[Finding]:
    """FROM t1, t2 — implicit comma join. Cartesian when no cross-table
    equality exists in the statement; style suggestion otherwise."""
    findings: list[Finding] = []
    for fm in re.finditer(r"\bfrom\b", cleaned, re.IGNORECASE):
        depth = depth_at[fm.start()]
        s_end = _scope_end(cleaned, depth_at, fm.end(), depth)
        b_end = s_end
        for bm in _FROM_BODY_BOUNDARY_RE.finditer(cleaned, fm.end(), s_end):
            if depth_at[bm.start()] == depth:
                b_end = bm.start()
                break
        parts = _split_top_level(cleaned[fm.end():b_end])
        if len(parts) < 2 or not all(_TABLE_ITEM_RE.match(p) for p in parts):
            continue
        stmt = cleaned[fm.end():s_end]
        has_link = any(
            m.group(1).strip("`").lower() != m.group(3).strip("`").lower()
            for m in _EQ_PAIR_RE.finditer(stmt)
        )
        line = line_of(sql, fm.start())
        if has_link:
            findings.append(Finding(
                severity=Severity.SUGGESTION,
                category="join_condition",
                description=f"行 {line} 使用逗号隐式 JOIN",
                location=f"行 {line}",
                impact="关联条件混在 WHERE 中，可读性差且易漏写",
                suggestion="改为显式 JOIN ... ON 写法",
            ))
        else:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                category="join_cartesian",
                description="逗号 JOIN 缺少关联条件（笛卡尔积）",
                location=f"行 {line}",
                impact="数据量爆炸/结果错误",
                suggestion="改为显式 JOIN ... ON 并补充关联条件",
            ))
    return findings


_NULL_EQ_RE = re.compile(r"(=|!=|<>)\s*null\b", re.IGNORECASE)


def _check_null_comparison(
    sql: str, cleaned: str, depth_at: list[int]
) -> list[Finding]:
    findings: list[Finding] = []
    for m in _NULL_EQ_RE.finditer(cleaned):
        op = m.group(1)
        fixed = "IS NULL" if op == "=" else "IS NOT NULL"
        findings.append(Finding(
            severity=Severity.CRITICAL,
            category="where_syntax",
            description=f"使用 {op} NULL 进行空值判断",
            location=f"行 {line_of(sql, m.start())}",
            impact="条件永远不成立，数据错误",
            suggestion=f"改为 {fixed}",
        ))
    return findings


_DIV_RE = re.compile(r"/\s*(`?[a-zA-Z_][\w.]*`?)\b(?!\s*\()")
_DIV_ZERO_RE = re.compile(r"/\s*0(?![\d.])")

_NON_COLUMN_WORDS = frozenset(
    ("null", "and", "or", "not", "case", "when", "then", "else", "end", "interval")
)


def _has_zero_guard(cleaned: str, denom: str) -> bool:
    """True when the denominator is compared against 0 somewhere (CASE guard)."""
    d = re.escape(denom.strip("`"))
    return bool(re.search(rf"\b{d}\s*(=|!=|<>|>)\s*0\b", cleaned, re.IGNORECASE))


def _check_division(sql: str, cleaned: str, depth_at: list[int]) -> list[Finding]:
    findings: list[Finding] = []
    for m in _DIV_ZERO_RE.finditer(cleaned):
        findings.append(Finding(
            severity=Severity.CRITICAL,
            category="calculation",
            description="除数为常量 0",
            location=f"行 {line_of(sql, m.start())}",
            impact="除零错误",
            suggestion="检查计算逻辑，避免除以 0",
        ))
    seen_lines: set[int] = set()
    for m in _DIV_RE.finditer(cleaned):
        denom = m.group(1).strip("`")
        if denom.lower() in _NON_COLUMN_WORDS:
            continue
        if _has_zero_guard(cleaned, denom):
            continue
        line = line_of(sql, m.start())
        if line in seen_lines:
            continue
        seen_lines.add(line)
        findings.append(Finding(
            severity=Severity.RISK,
            category="calculation",
            description=f"除法运算 / {m.group(1)} 未做除零保护",
            location=f"行 {line}",
            impact="除数为 0 或 NULL 时结果异常",
            suggestion=f"改为 / NULLIF({m.group(1)}, 0)",
        ))
    return findings


@lru_cache(maxsize=8)
def _partition_filter_re(cols: tuple[str, ...]) -> re.Pattern[str]:
    # cols come from user config — escape so metachars can't break the pattern
    alts = "|".join(re.escape(c) for c in cols)
    return re.compile(
        rf"(?:(\w+)\s*\.\s*)?\b({alts})\s*"
        rf"(=|>=|<=|>|<|\bbetween\b|\bin\b)",
        re.IGNORECASE,
    )


def _check_partition_filter(
    sql: str, cleaned: str, depth_at: list[int], dialect: str, config: ReviewConfig
) -> list[Finding]:
    if dialect not in BATCH_WAREHOUSES:
        return []
    findings: list[Finding] = []

    # A qualified filter (a.pt = ...) only covers its own table/alias; an
    # unqualified filter (pt = ...) is ambiguous, so it covers everything.
    has_bare_filter = False
    qualified: set[str] = set()
    for m in _partition_filter_re(config.partition_cols).finditer(cleaned):
        if m.group(1):
            qualified.add(m.group(1).lower())
        else:
            has_bare_filter = True
    if has_bare_filter:
        return []

    ctes = _cte_names(cleaned)
    reported: set[str] = set()
    for off, name, alias in _extract_table_refs(cleaned):
        base = name.split(".")[-1]
        if name in ctes or name in reported:
            continue
        if not any(base.endswith(sfx) for sfx in config.incremental_suffixes):
            continue
        if qualified & {q for q in (alias, base, name) if q}:
            continue
        reported.add(name)
        findings.append(Finding(
            severity=Severity.RISK,
            category="partition_pruning",
            description=f"表 {name} 缺少分区过滤条件",
            location=f"行 {line_of(sql, off)}",
            impact="全表扫描",
            suggestion="添加分区条件如 pt = '${bizdate}'",
        ))
    return findings


def _check_partition_value_quoting(
    sql: str, cleaned: str, depth_at: list[int], dialect: str, config: ReviewConfig
) -> list[Finding]:
    if dialect not in BATCH_WAREHOUSES:
        return []
    findings: list[Finding] = []
    for col in config.partition_cols:
        for m in re.finditer(
            rf"\b{re.escape(col)}\s*=\s*(\d{{6,8}})\b", cleaned, re.IGNORECASE
        ):
            findings.append(Finding(
                severity=Severity.RISK,
                category="where_partition",
                description=f"分区条件 {col} = {m.group(1)} 使用了数值而非字符串",
                location=f"行 {line_of(sql, m.start())}",
                impact="隐式类型转换可能导致分区裁剪失效",
                suggestion=f"改为 {col} = '{m.group(1)}'",
            ))
    return findings


def _check_select_star(
    sql: str, cleaned: str, depth_at: list[int]
) -> list[Finding]:
    findings: list[Finding] = []
    for m in re.finditer(r"\bselect\s+(?:all\s+)?\*(?!\w)", cleaned, re.IGNORECASE):
        findings.append(Finding(
            severity=Severity.RISK,
            category="resource_usage",
            description="使用 SELECT * 读取全部字段",
            location=f"行 {line_of(sql, m.start())}",
            impact="不必要的大表扫描 / 列裁剪失效",
            suggestion="只 SELECT 需要的字段",
        ))
    return findings


def _check_order_by_no_limit(
    sql: str, cleaned: str, depth_at: list[int], dialect: str, config: ReviewConfig
) -> list[Finding]:
    # streaming has no global sort; OLTP result sets are small enough
    # that a bare ORDER BY is normal
    if dialect == "flink" or dialect in OLTP:
        return []
    findings: list[Finding] = []
    for m in re.finditer(r"\border\s+by\b", cleaned, re.IGNORECASE):
        if depth_at[m.start()] != 0:
            continue
        stmt_end = _scope_end(cleaned, depth_at, m.end(), 0)
        limit_re = re.compile(r"\blimit\s+\d+", re.IGNORECASE)
        has_limit = any(
            depth_at[lm.start()] == 0
            for lm in limit_re.finditer(cleaned, m.end(), stmt_end)
        )
        if not has_limit:
            findings.append(Finding(
                severity=Severity.RISK,
                category="resource_usage",
                description="ORDER BY 全局排序且没有 LIMIT",
                location=f"行 {line_of(sql, m.start())}",
                impact="单 reducer 全局排序，性能极差",
                suggestion="添加 LIMIT，或改用 SORT BY / DISTRIBUTE BY",
            ))
    return findings


def _check_union(sql: str, cleaned: str, depth_at: list[int]) -> list[Finding]:
    findings: list[Finding] = []
    for m in re.finditer(r"\bunion\b(?!\s+all)", cleaned, re.IGNORECASE):
        findings.append(Finding(
            severity=Severity.SUGGESTION,
            category="resource_usage",
            description=f"行 {line_of(sql, m.start())} 使用 UNION 会触发去重",
            location=f"行 {line_of(sql, m.start())}",
            impact="额外的去重开销",
            suggestion="确认是否需要去重；不需要时改用 UNION ALL",
        ))
    return findings


def _check_count_distinct(
    sql: str, cleaned: str, depth_at: list[int], dialect: str, config: ReviewConfig
) -> list[Finding]:
    # data skew is a distributed-engine concern
    if dialect in OLTP:
        return []
    findings: list[Finding] = []
    for m in re.finditer(r"\bcount\s*\(\s*distinct\b", cleaned, re.IGNORECASE):
        findings.append(Finding(
            severity=Severity.SUGGESTION,
            category="data_skew",
            description=f"行 {line_of(sql, m.start())} 使用 COUNT(DISTINCT)，大数据量下易倾斜",
            location=f"行 {line_of(sql, m.start())}",
            impact="单点聚合可能倾斜",
            suggestion="数据量大时可改为两阶段 GROUP BY 去重再计数",
        ))
    return findings


def _check_insert_overwrite(
    sql: str, cleaned: str, depth_at: list[int], dialect: str, config: ReviewConfig
) -> list[Finding]:
    if dialect not in BATCH_WAREHOUSES:
        return []
    findings: list[Finding] = []
    for m in re.finditer(r"\binsert\s+overwrite\s+table\s+([`\w.]+)", cleaned, re.IGNORECASE):
        tail = cleaned[m.end(): m.end() + 120]
        if not re.match(r"\s*partition\s*\(", tail, re.IGNORECASE):
            findings.append(Finding(
                severity=Severity.RISK,
                category="where_partition",
                description=f"INSERT OVERWRITE {m.group(1)} 未指定 PARTITION",
                location=f"行 {line_of(sql, m.start())}",
                impact="将覆盖整张表数据",
                suggestion="指定 PARTITION(pt='${bizdate}') 只覆盖目标分区",
            ))
    return findings


def _check_dml_without_where(
    sql: str, cleaned: str, depth_at: list[int], dialect: str, config: ReviewConfig
) -> list[Finding]:
    """UPDATE / DELETE with no top-level WHERE — full-table write."""
    findings: list[Finding] = []
    dml_re = re.compile(
        r"\b(?:(update)\s+([`\w.]+)|(delete)\s+from\s+([`\w.]+))\b",
        re.IGNORECASE,
    )
    for m in dml_re.finditer(cleaned):
        if depth_at[m.start()] != 0:
            continue
        # skip UPDATE keywords that are not statements: "SELECT ... FOR
        # UPDATE" (lock hint), "FOR NO KEY UPDATE" (PG), and MySQL's
        # "INSERT ... ON DUPLICATE KEY UPDATE"
        if m.group(1) and re.search(
            r"\b(?:for|key)\s*$", cleaned[:m.start()], re.IGNORECASE
        ):
            continue
        verb = (m.group(1) or m.group(3)).upper()
        table = m.group(2) or m.group(4)
        has_where = any(
            depth_at[w.start()] == 0
            for w in re.finditer(r"\bwhere\b", cleaned, re.IGNORECASE)
            if w.start() > m.end()
        )
        if not has_where:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                category="where_syntax",
                description=f"{verb} {table} 没有 WHERE 条件",
                location=f"行 {line_of(sql, m.start())}",
                impact="将更新/删除整张表的数据",
                suggestion="添加 WHERE 条件限定范围；确需全表操作请显式注释说明",
            ))
    return findings


def _check_leading_wildcard_like(
    sql: str, cleaned: str, depth_at: list[int], dialect: str, config: ReviewConfig
) -> list[Finding]:
    """LIKE '%xxx' defeats index usage on row stores."""
    if dialect not in OLTP:
        return []
    findings: list[Finding] = []
    for m in re.finditer(r"\bi?like\b", cleaned, re.IGNORECASE):
        # literals are blanked in `cleaned` (as spaces), so skip whitespace in
        # the ORIGINAL sql and read the pattern's first characters from there
        i = m.end()
        while i < len(sql) and sql[i] in " \t\r\n":
            i += 1
        if sql[i:i + 2] in ("'%", '"%'):
            findings.append(Finding(
                severity=Severity.RISK,
                category="resource_usage",
                description="LIKE 使用前导通配符 '%...'",
                location=f"行 {line_of(sql, m.start())}",
                impact="无法使用索引，触发全表扫描",
                suggestion="尽量改为前缀匹配 'xxx%'，或使用全文索引",
            ))
    return findings


_WHERE_FUNC_RE = re.compile(
    r"\b(date|year|month|day|substr|substring|date_format|to_char|"
    r"date_trunc|trunc|lower|upper|left|right)\s*\(\s*[`\w.]+\s*[,)]",
    re.IGNORECASE,
)
_CLAUSE_END_RE = re.compile(
    r"\b(group\s+by|order\s+by|limit|having|union|window)\b", re.IGNORECASE,
)


def _check_where_func_on_column(
    sql: str, cleaned: str, depth_at: list[int], dialect: str, config: ReviewConfig
) -> list[Finding]:
    """Function wrapped around a column inside WHERE — index cannot be used."""
    if dialect not in OLTP:
        return []
    findings: list[Finding] = []
    for w in re.finditer(r"\bwhere\b", cleaned, re.IGNORECASE):
        base_depth = depth_at[w.start()]
        end_m = _CLAUSE_END_RE.search(cleaned, w.end())
        end = end_m.start() if end_m else len(cleaned)
        for m in _WHERE_FUNC_RE.finditer(cleaned, w.end(), end):
            if depth_at[m.start()] != base_depth:
                continue
            findings.append(Finding(
                severity=Severity.SUGGESTION,
                category="resource_usage",
                description=f"WHERE 条件对列使用函数 {m.group(1).upper()}(...)",
                location=f"行 {line_of(sql, m.start())}",
                impact="列上函数使索引失效，可能全表扫描",
                suggestion="改写为对常量侧计算的范围条件，如 col >= '...' AND col < '...'",
            ))
    return findings


def _check_deep_offset(
    sql: str, cleaned: str, depth_at: list[int], dialect: str, config: ReviewConfig
) -> list[Finding]:
    """LIMIT big_offset, n / OFFSET big_n — deep pagination scans and discards."""
    if dialect == "flink":
        return []
    findings: list[Finding] = []
    for m in re.finditer(
        r"\blimit\s+(\d+)\s*,\s*\d+|\boffset\s+(\d+)\b", cleaned, re.IGNORECASE
    ):
        off = int(m.group(1) or m.group(2))
        if off < config.deep_offset_threshold:
            continue
        findings.append(Finding(
            severity=Severity.RISK,
            category="resource_usage",
            description=f"深分页 OFFSET {off}",
            location=f"行 {line_of(sql, m.start())}",
            impact=f"需要扫描并丢弃前 {off} 行，越翻越慢",
            suggestion="改用游标分页（WHERE id > 上页末尾 id ORDER BY id LIMIT n）",
        ))
    return findings


def _check_clickhouse_final(
    sql: str, cleaned: str, depth_at: list[int], dialect: str, config: ReviewConfig
) -> list[Finding]:
    if dialect != "clickhouse":
        return []
    findings: list[Finding] = []
    for m in re.finditer(
        r"\b(?:from|join)\s+[`\w.]+\s+final\b", cleaned, re.IGNORECASE
    ):
        findings.append(Finding(
            severity=Severity.RISK,
            category="resource_usage",
            description="查询使用了 FINAL 修饰符",
            location=f"行 {line_of(sql, m.start())}",
            impact="FINAL 强制读时合并，显著降低查询性能",
            suggestion="改用 argMax / GROUP BY 取最新版本，或依赖后台 merge",
        ))
    return findings


def _check_readability(
    sql: str, cleaned: str, depth_at: list[int], config: ReviewConfig
) -> list[Finding]:
    lines = sql.count("\n") + 1
    has_comment = "--" in sql or "/*" in sql
    if lines >= config.readability_min_lines and not has_comment:
        return [Finding(
            severity=Severity.SUGGESTION,
            category="readability",
            description="SQL 较长但没有任何注释",
            location="全局",
            impact="可读性差",
            suggestion="为复杂逻辑段落添加注释说明",
        )]
    return []


def _check_distinct_with_groupby(
    sql: str, cleaned: str, depth_at: list[int]
) -> list[Finding]:
    findings: list[Finding] = []
    for m in re.finditer(r"\bselect\s+distinct\b", cleaned, re.IGNORECASE):
        rest = cleaned[m.end():]
        gb = re.search(r"\bgroup\s+by\b", rest, re.IGNORECASE)
        sub = re.search(r"\bselect\b", rest, re.IGNORECASE)
        if gb and (not sub or gb.start() < sub.start()):
            findings.append(Finding(
                severity=Severity.SUGGESTION,
                category="dedup",
                description=f"行 {line_of(sql, m.start())} DISTINCT 与 GROUP BY 同时使用",
                location=f"行 {line_of(sql, m.start())}",
                impact="冗余去重",
                suggestion="GROUP BY 已保证去重，可去掉 DISTINCT",
            ))
    return findings


# ---------------------------------------------------------------------------
# Complexity scoring — thresholds come from ReviewConfig (.sqlreview.yaml)
# ---------------------------------------------------------------------------

_SUBQ_OPEN_RE = re.compile(r"\s*select\b", re.IGNORECASE)


def _subquery_depth(cleaned: str) -> int:
    stack: list[bool] = []
    depth = max_depth = 0
    for i, ch in enumerate(cleaned):
        if ch == "(":
            is_sub = bool(_SUBQ_OPEN_RE.match(cleaned, i + 1))
            stack.append(is_sub)
            if is_sub:
                depth += 1
                max_depth = max(max_depth, depth)
        elif ch == ")" and stack:
            if stack.pop():
                depth -= 1
    return max_depth


def _check_complexity(
    sql: str, cleaned: str, depth_at: list[int], config: ReviewConfig
) -> list[Finding]:
    findings: list[Finding] = []
    subq = _subquery_depth(cleaned)
    if subq > config.max_subquery_depth:
        findings.append(Finding(
            severity=Severity.SUGGESTION,
            category="readability",
            description=f"子查询嵌套达 {subq} 层（阈值 {config.max_subquery_depth}）",
            location="行 1",
            impact="嵌套过深难以阅读和维护，优化器也难以优化",
            suggestion="用 WITH（CTE）把子查询拆平",
        ))
    joins = len(re.findall(r"\bjoin\b", cleaned, re.IGNORECASE))
    if joins > config.max_joins:
        findings.append(Finding(
            severity=Severity.SUGGESTION,
            category="readability",
            description=f"单条语句包含 {joins} 个 JOIN（阈值 {config.max_joins}）",
            location="行 1",
            impact="过多 JOIN 使执行计划复杂、排查困难",
            suggestion="拆分为中间表/CTE，分步落地",
        ))
    lines = sql.count("\n") + 1
    if lines > config.max_stmt_lines:
        findings.append(Finding(
            severity=Severity.SUGGESTION,
            category="readability",
            description=f"单条语句长达 {lines} 行（阈值 {config.max_stmt_lines}）",
            location="行 1",
            impact="超长语句难以 review 与维护",
            suggestion="拆分为多个步骤或视图",
        ))
    return findings


_RULES = (
    _check_groupby_completeness,
    _check_joins,
    _check_comma_join,
    _check_null_comparison,
    _check_division,
    _check_select_star,
    _check_union,
    _check_distinct_with_groupby,
)

# rules that read thresholds from ReviewConfig
_CONFIG_RULES = (
    _check_readability,
    _check_complexity,
)

_DIALECT_RULES = (
    _check_partition_filter,
    _check_partition_value_quoting,
    _check_order_by_no_limit,
    _check_insert_overwrite,
    _check_count_distinct,
    _check_dml_without_where,
    _check_leading_wildcard_like,
    _check_where_func_on_column,
    _check_deep_offset,
    _check_clickhouse_final,
)


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
