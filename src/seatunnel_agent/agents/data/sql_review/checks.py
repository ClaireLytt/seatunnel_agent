"""Deterministic static lint rules for SQL code review.

Each ``_check_*`` function is a regex/scanner based rule, best-effort and
biased toward high-precision findings. All rules operate on a
length-preserving cleaned copy of the SQL so match offsets map back to
original line numbers. Orchestration lives in linter.py.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from .config import ReviewConfig
from .report import Finding, Severity
from .sqlparse_util import (
    _bare_column,
    _cte_names,
    _extract_table_refs,
    _find_keyword_positions,
    _is_aggregate_expr,
    _norm_expr,
    _scope_end,
    _split_alias,
    _split_top_level,
    _type_family,
    line_of,
)

# Engine families — rules gate on these instead of listing dialects inline.
# BATCH_WAREHOUSES: partitioned batch engines where partition pruning /
# INSERT OVERWRITE PARTITION semantics apply. OLTP: row stores where index
# usage matters and global ORDER BY is normal.
BATCH_WAREHOUSES = frozenset({"hive", "spark", "maxcompute"})
OLTP = frozenset({"mysql", "postgresql", "sqlserver", "sqlite"})
OLAP_MPP = frozenset({"clickhouse", "doris"})

_CLAUSE_KEYWORDS_RE = re.compile(
    r"\b(having|order\s+by|limit|window|union|cluster\s+by|distribute\s+by|sort\s+by|qualify)\b",
    re.IGNORECASE,
)


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
                key="groupby_missing", args={"cols": ", ".join(missing)},
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
                key="cross_join",
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
                key="join_no_on",
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
                    key="join_on_or",
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
                    key="join_non_equi",
                ))
    return findings


_EQ_PAIR_RE = re.compile(
    r"(`?\w+`?)\s*\.\s*(`?\w+`?)\s*=\s*(`?\w+`?)\s*\.\s*(`?\w+`?)"
)


def _resolve_tables(
    cleaned: str, store: Any
) -> tuple[dict[str, Any], list[tuple[int, str, str | None]], set[str]]:
    """Map alias / bare name / full name -> TableSchema for every FROM/JOIN
    reference that resolves in the store. Also returns the raw refs and the
    CTE names so callers can tell "unknown" from "not a physical table"."""
    ctes = _cte_names(cleaned)
    refs = _extract_table_refs(cleaned)
    resolve: dict[str, Any] = {}
    for _off, name, alias in refs:
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
    return resolve, refs, ctes


def _check_join_key_types(
    sql: str, cleaned: str, depth_at: list[int], store: Any
) -> list[Finding]:
    """Schema-aware: flag equality comparisons whose column type families differ
    (e.g. string = bigint). Only runs when a SchemaStore is available."""
    if store is None or len(store) == 0:
        return []
    resolve, _refs, _ctes = _resolve_tables(cleaned, store)

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
            key="join_key_type",
            args={"left": f"{lq}.{lc}", "ltype": lcol.dtype,
                  "right": f"{rq}.{rc}", "rtype": rcol.dtype},
        ))
    return findings


_QUAL_COL_RE = re.compile(r"(`?\w+`?)\s*\.\s*(`?\w+`?)")
_QUAL_STAR_RE = re.compile(r"(`?\w+`?)\s*\.\s*\*")
_BARE_STAR_RE = re.compile(r"\bselect\s+\*", re.IGNORECASE)


def _check_schema_refs(
    sql: str, cleaned: str, depth_at: list[int], store: Any,
    config: ReviewConfig,
) -> list[Finding]:
    """Schema-aware: unknown tables/columns, SELECT * on wide tables, and
    filters that look like partition pruning but hit a non-partition column.
    Only runs when a SchemaStore is available."""
    if store is None or len(store) == 0:
        return []
    resolve, refs, ctes = _resolve_tables(cleaned, store)
    findings: list[Finding] = []

    # ── unknown table ──
    seen_tables: set[str] = set()
    for off, name, _alias in refs:
        if name in ctes or name in seen_tables:
            continue
        seen_tables.add(name)
        base = name.split(".")[-1]
        if store.get(name) is not None or any(
            t.name.lower() == base for t in store.tables
        ):
            continue
        findings.append(Finding(
            severity=Severity.RISK,
            category="schema_ref",
            description=f"表 {name} 在提供的 schema 中不存在",
            location=f"行 {line_of(sql, off)}",
            impact="语句将执行失败，或 schema 信息已过期",
            suggestion="检查表名，或更新 DDL / 数据库连接",
            key="unknown_table", args={"table": name},
        ))

    # ── unknown qualified column ──
    seen_cols: set[tuple[str, str]] = set()
    for m in _QUAL_COL_RE.finditer(cleaned):
        qual, col = (g.strip("`").lower() for g in m.groups())
        table = resolve.get(qual)
        if table is None or col.isdigit():
            continue
        # skip when the match is itself a table reference (db.table)
        if resolve.get(f"{qual}.{col}") is not None:
            continue
        if table.find_column(col) is not None:
            continue
        key = (table.full_name.lower(), col)
        if key in seen_cols:
            continue
        seen_cols.add(key)
        findings.append(Finding(
            severity=Severity.RISK,
            category="schema_ref",
            description=f"列 {col} 在表 {table.full_name} 中不存在",
            location=f"行 {line_of(sql, m.start())}",
            impact="语句将执行失败，或 schema 信息已过期",
            suggestion="对照表定义检查列名",
            key="unknown_column",
            args={"column": col, "table": table.full_name},
        ))

    # ── SELECT * on a wide table ──
    resolved_tables = {id(t): t for t in resolve.values()}
    seen_star: set[str] = set()

    def star_finding(table: Any, off: int) -> None:
        n = len(table.columns) + len(table.partition_columns)
        if n < config.select_star_wide_cols or table.full_name.lower() in seen_star:
            return
        seen_star.add(table.full_name.lower())
        findings.append(Finding(
            severity=Severity.RISK,
            category="resource_usage",
            description=f"对 {table.full_name} 使用 SELECT * 将展开为 {n} 列",
            location=f"行 {line_of(sql, off)}",
            impact="读取远超实际所需的数据量",
            suggestion="只选择需要的列",
            key="select_star_wide",
            args={"table": table.full_name, "n": n},
        ))

    for m in _QUAL_STAR_RE.finditer(cleaned):
        table = resolve.get(m.group(1).strip("`").lower())
        if table is not None:
            star_finding(table, m.start())
    single = (next(iter(resolved_tables.values()))
              if len(resolved_tables) == 1 else None)
    if single is not None:
        for m in _BARE_STAR_RE.finditer(cleaned):
            star_finding(single, m.start())

    # ── filter on a pseudo partition column ──
    if config.partition_cols:
        cols_alt = "|".join(re.escape(c) for c in config.partition_cols)
        part_re = re.compile(
            rf"(?:(`?\w+`?)\s*\.\s*)?\b({cols_alt})\b"
            rf"(?:\s*(?:=|!=|<>|>=|<=|<|>)|\s+(?:in|between|like)\b)",
            re.IGNORECASE,
        )
        seen_part: set[tuple[str, str]] = set()
        for m in part_re.finditer(cleaned):
            qual = (m.group(1) or "").strip("`").lower()
            col = m.group(2).lower()
            table = resolve.get(qual) if qual else single
            if table is None or not table.is_partitioned:
                continue
            parts = [c.name for c in table.partition_columns]
            if col in {p.lower() for p in parts}:
                continue
            key = (table.full_name.lower(), col)
            if key in seen_part:
                continue
            seen_part.add(key)
            parts_str = ", ".join(parts)
            findings.append(Finding(
                severity=Severity.RISK,
                category="partition_pruning",
                description=(
                    f"{col} 被当作分区列过滤，但 {table.full_name} 并未按它分区"
                ),
                location=f"行 {line_of(sql, m.start(2))}",
                impact="该条件无法裁剪分区",
                suggestion=f"改用表的真实分区列过滤：{parts_str}",
                key="not_partition_column",
                args={"col": col, "table": table.full_name,
                      "parts": parts_str},
            ))

    # ── DDL-known partitioned table without a partition filter ──
    # The name-suffix heuristic in _check_partition_filter only covers
    # incremental tables; when the DDL says a table is partitioned we can
    # require the filter regardless of naming (and skip suffix-matched
    # tables there to avoid duplicate findings).
    reported_part: set[str] = set()
    for off, name, alias in refs:
        if name in ctes or name in reported_part:
            continue
        table = store.get(name)
        if table is None or not table.is_partitioned:
            continue
        base = name.split(".")[-1]
        if any(base.endswith(sfx) for sfx in config.incremental_suffixes):
            continue                      # covered by _check_partition_filter
        parts = tuple(c.name for c in table.partition_columns)
        covered = False
        for m in _partition_filter_re(parts).finditer(cleaned):
            qual = (m.group(1) or "").lower()
            if not qual or qual in {q for q in (alias, base, name.lower()) if q}:
                covered = True
                break
        if covered:
            continue
        reported_part.add(name)
        parts_str = ", ".join(parts)
        findings.append(Finding(
            severity=Severity.RISK,
            category="partition_pruning",
            description=f"表 {name} 缺少分区过滤条件",
            location=f"行 {line_of(sql, off)}",
            impact="全表扫描",
            suggestion=f"添加分区条件，分区列：{parts_str}",
            key="partition_missing", args={"table": name},
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
                key="comma_join_style", args={"line": line},
            ))
        else:
            findings.append(Finding(
                severity=Severity.CRITICAL,
                category="join_cartesian",
                description="逗号 JOIN 缺少关联条件（笛卡尔积）",
                location=f"行 {line}",
                impact="数据量爆炸/结果错误",
                suggestion="改为显式 JOIN ... ON 并补充关联条件",
                key="comma_join_cartesian",
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
            key="null_eq", args={"op": op, "fixed": fixed},
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
            key="div_zero_const",
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
            key="div_no_guard", args={"denom": m.group(1)},
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
            key="partition_missing", args={"table": name},
        ))
    return findings


def _check_partition_func_filter(
    sql: str, cleaned: str, depth_at: list[int], dialect: str, config: ReviewConfig
) -> list[Finding]:
    """Function wrapped around a partition column — pruning is defeated.

    The classic batch-warehouse anti-pattern: ``substr(dt, 1, 7) = '2024-06'``
    scans every partition.  (OLTP engines get the analogous index-oriented
    rule from ``_check_where_func_on_column``.)"""
    if dialect not in BATCH_WAREHOUSES:
        return []
    findings: list[Finding] = []
    cols_alt = "|".join(re.escape(c) for c in config.partition_cols)
    pat = re.compile(
        rf"\b(\w+)\s*\(\s*(?:`?\w+`?\s*\.\s*)?`?({cols_alt})`?\s*[,)]",
        re.IGNORECASE,
    )
    # `dt IN (...)` and similar are predicates, not function calls
    not_funcs = {"in", "and", "or", "not", "on", "where", "exists",
                 "between", "values", "by"}
    seen: set[tuple[str, str]] = set()
    for w in re.finditer(r"\bwhere\b", cleaned, re.IGNORECASE):
        end_m = _CLAUSE_END_RE.search(cleaned, w.end())
        end = end_m.start() if end_m else len(cleaned)
        for m in pat.finditer(cleaned, w.end(), end):
            func, col = m.group(1).upper(), m.group(2).lower()
            if func.lower() in not_funcs or (func, col) in seen:
                continue
            seen.add((func, col))
            findings.append(Finding(
                severity=Severity.RISK,
                category="partition_pruning",
                description=f"对分区列 {col} 使用函数 {func}(...) 过滤",
                location=f"行 {line_of(sql, m.start())}",
                impact="分区裁剪失效，全表扫描",
                suggestion=f"改为对常量侧计算的范围条件，如 {col} >= '...' AND {col} < '...'",
                key="partition_func_on_col", args={"func": func, "col": col},
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
                key="partition_numeric", args={"col": col, "val": m.group(1)},
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
            key="select_star",
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
                key="order_by_no_limit",
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
            key="union_dedup", args={"line": line_of(sql, m.start())},
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
            key="count_distinct", args={"line": line_of(sql, m.start())},
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
                key="insert_overwrite_no_partition", args={"table": m.group(1)},
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
                key="dml_no_where", args={"verb": verb, "table": table},
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
                key="leading_wildcard_like",
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
                key="where_func_on_column", args={"func": m.group(1).upper()},
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
            key="deep_offset", args={"off": off},
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
            key="clickhouse_final",
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
            key="readability_no_comment",
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
                key="distinct_with_groupby",
                args={"line": line_of(sql, m.start())},
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
            key="subquery_depth",
            args={"depth": subq, "max": config.max_subquery_depth},
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
            key="too_many_joins",
            args={"joins": joins, "max": config.max_joins},
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
            key="stmt_too_long",
            args={"lines": lines, "max": config.max_stmt_lines},
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
    _check_partition_func_filter,
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
