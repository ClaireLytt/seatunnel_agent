# -*- coding: utf-8 -*-
"""Core AST-level caliber comparison of two SQL statements.

Extracts, per statement: source tables, join types/conditions, WHERE
conjuncts (time-range predicates classified separately), GROUP BY keys,
output expressions (aggregates flagged), dedup mechanisms (DISTINCT /
row_number()=1 / GROUP BY), HAVING and LIMIT — then diffs the two sides
category by category.

Deterministic only — no LLM, no database, nothing executed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp

# Caliber categories, in report order.
CAT_SOURCE = "source"          # different source tables
CAT_JOIN = "join"              # join type / condition differs
CAT_FILTER = "filter"          # WHERE conjunct present on one side only
CAT_TIME = "time_range"        # time/partition range differs
CAT_AGG = "aggregation"        # aggregate expression / GROUP BY differs
CAT_DEDUP = "dedup"            # DISTINCT vs row_number vs none
CAT_LIMIT = "limit"            # LIMIT / HAVING differs
CAT_OUTPUT = "output"          # output-only difference (aliases, extra cols)

# Severity levels (align with schema_drift wording).
SEV_CRITICAL = "critical"      # almost certainly changes the number
SEV_RISK = "risk"              # may change the number
SEV_INFO = "info"              # cosmetic / output-only

_SEVERITY_ORDER = {SEV_CRITICAL: 0, SEV_RISK: 1, SEV_INFO: 2}

_TIME_COL_HINTS = re.compile(
    r"(^|_)(dt|pt|ds|date|day|time|hour|month|week|created?_at|updated?_at)($|_)",
    re.IGNORECASE)
_DATE_LITERAL = re.compile(r"\d{4}-\d{2}-\d{2}|\d{8}")


@dataclass
class Finding:
    category: str
    severity: str
    key: str                   # message key in RECONCILE_I18N
    args: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"category": self.category, "severity": self.severity,
                "key": self.key, "args": dict(self.args)}


@dataclass
class SqlProfile:
    """One statement's caliber-relevant shape."""
    tables: list[str] = field(default_factory=list)
    joins: list[dict[str, str]] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    time_filters: list[str] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    aggregates: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    distinct: bool = False
    row_number_dedup: bool = False
    having: str = ""
    limit: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tables": self.tables, "joins": self.joins,
            "filters": self.filters, "time_filters": self.time_filters,
            "group_by": self.group_by, "aggregates": self.aggregates,
            "outputs": self.outputs, "distinct": self.distinct,
            "row_number_dedup": self.row_number_dedup,
            "having": self.having, "limit": self.limit,
        }


@dataclass
class ReconcileReport:
    findings: list[Finding] = field(default_factory=list)
    profile_a: SqlProfile = field(default_factory=SqlProfile)
    profile_b: SqlProfile = field(default_factory=SqlProfile)
    dialect: str = "hive"
    parse_error: str = ""

    @property
    def identical(self) -> bool:
        return not self.findings and not self.parse_error

    def counts(self) -> dict[str, int]:
        c = {SEV_CRITICAL: 0, SEV_RISK: 0, SEV_INFO: 0}
        for f in self.findings:
            c[f.severity] += 1
        return c

    def worst_level(self) -> str | None:
        if not self.findings:
            return None
        return min((f.severity for f in self.findings),
                   key=lambda s: _SEVERITY_ORDER[s])


def _norm(node: exp.Expression) -> str:
    """Normalized, comparable SQL text for an AST node."""
    return re.sub(r"\s+", " ", node.sql(normalize=True)).strip().lower()


def _flatten_and(node: exp.Expression | None) -> list[exp.Expression]:
    if node is None:
        return []
    if isinstance(node, exp.And):
        return _flatten_and(node.left) + _flatten_and(node.right)
    if isinstance(node, exp.Paren):
        return _flatten_and(node.this)
    return [node]


def _is_time_predicate(node: exp.Expression) -> bool:
    for col in node.find_all(exp.Column):
        if _TIME_COL_HINTS.search(col.name or ""):
            return True
    return bool(_DATE_LITERAL.search(node.sql()))


def _alias_map(select: exp.Select) -> dict[str, str]:
    """alias -> real table name, so join/filter text is alias-independent."""
    mapping: dict[str, str] = {}
    for table in select.find_all(exp.Table):
        name = table.name.lower()
        alias = (table.alias or name).lower()
        mapping[alias] = name
    return mapping


def _resolve_aliases(node: exp.Expression, aliases: dict[str, str]) -> exp.Expression:
    node = node.copy()
    for col in node.find_all(exp.Column):
        tbl = (col.table or "").lower()
        if tbl in aliases:
            col.set("table", exp.to_identifier(aliases[tbl]))
    return node


def _profile_select(select: exp.Select) -> SqlProfile:
    prof = SqlProfile()
    aliases = _alias_map(select)

    # Source tables (subquery sources profiled as their inner tables too).
    prof.tables = sorted({t.name.lower() for t in select.find_all(exp.Table)})

    # Joins: type + alias-resolved ON condition.
    for join in select.find_all(exp.Join):
        kind = " ".join(p for p in (join.args.get("side") or "",
                                    join.args.get("kind") or "join") if p).lower()
        on = join.args.get("on")
        cond = _norm(_resolve_aliases(on, aliases)) if on is not None else ""
        target = join.this
        tname = target.name.lower() if isinstance(target, exp.Table) else _norm(target)
        prof.joins.append({"type": kind.strip() or "join",
                           "table": tname, "condition": cond})
    prof.joins.sort(key=lambda j: (j["table"], j["condition"]))

    # WHERE conjuncts, time-range predicates split out.
    where = select.args.get("where")
    for pred in _flatten_and(where.this if where is not None else None):
        resolved = _resolve_aliases(pred, aliases)
        text = _norm(resolved)
        # row_number()=1 style dedup pushed down as a filter
        if "row_number" in text or "rank(" in text:
            prof.row_number_dedup = True
            continue
        if _is_time_predicate(pred):
            prof.time_filters.append(text)
        else:
            prof.filters.append(text)
    prof.filters.sort()
    prof.time_filters.sort()

    # QUALIFY row_number() (Spark/StarRocks) also counts as dedup.
    if select.args.get("qualify") is not None:
        prof.row_number_dedup = True
    # row_number inside a subquery filtered outside — common Hive dedup.
    for window in select.find_all(exp.Window):
        fn = window.this
        if isinstance(fn, exp.RowNumber) or (
                isinstance(fn, exp.Anonymous)
                and fn.name.lower() == "row_number"):
            prof.row_number_dedup = True

    prof.distinct = bool(select.args.get("distinct"))

    group = select.args.get("group")
    if group is not None:
        prof.group_by = sorted(
            _norm(_resolve_aliases(e, aliases)) for e in group.expressions)

    for proj in select.expressions:
        inner = proj.unalias() if isinstance(proj, exp.Alias) else proj
        resolved = _resolve_aliases(inner, aliases)
        text = _norm(resolved)
        prof.outputs.append(text)
        if list(inner.find_all(exp.AggFunc)):
            prof.aggregates.append(text)
    prof.outputs.sort()
    prof.aggregates.sort()

    having = select.args.get("having")
    if having is not None:
        prof.having = _norm(_resolve_aliases(having.this, aliases))
    limit = select.args.get("limit")
    if limit is not None:
        prof.limit = _norm(limit.expression)
    return prof


def profile_sql(sql: str, dialect: str = "hive") -> SqlProfile:
    """Profile the outermost SELECT of one statement."""
    tree = sqlglot.parse_one(sql, read=dialect)
    select = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
    if select is None:
        raise ValueError("no SELECT found")
    return _profile_select(select)


def _diff_sets(a: list[str], b: list[str]) -> tuple[list[str], list[str]]:
    sa, sb = set(a), set(b)
    return sorted(sa - sb), sorted(sb - sa)


def reconcile_sql(sql_a: str, sql_b: str,
                  dialect: str = "hive") -> ReconcileReport:
    """Compare two SQL statements caliber by caliber."""
    report = ReconcileReport(dialect=dialect)
    try:
        report.profile_a = profile_sql(sql_a, dialect)
        report.profile_b = profile_sql(sql_b, dialect)
    except (sqlglot.errors.ParseError, ValueError) as err:
        report.parse_error = str(err).splitlines()[0]
        return report
    a, b = report.profile_a, report.profile_b
    out = report.findings

    # 1. Source tables.
    only_a, only_b = _diff_sets(a.tables, b.tables)
    if only_a or only_b:
        out.append(Finding(CAT_SOURCE, SEV_CRITICAL, "msg_tables_differ",
                           {"only_a": ", ".join(only_a) or "-",
                            "only_b": ", ".join(only_b) or "-"}))

    # 2. Joins — compare by target table.
    joins_a = {j["table"]: j for j in a.joins}
    joins_b = {j["table"]: j for j in b.joins}
    for tbl in sorted(set(joins_a) | set(joins_b)):
        ja, jb = joins_a.get(tbl), joins_b.get(tbl)
        if ja is None or jb is None:
            side = "A" if ja is not None else "B"
            out.append(Finding(CAT_JOIN, SEV_CRITICAL, "msg_join_only",
                               {"table": tbl, "side": side}))
        else:
            if ja["type"] != jb["type"]:
                out.append(Finding(CAT_JOIN, SEV_CRITICAL, "msg_join_type",
                                   {"table": tbl, "a": ja["type"],
                                    "b": jb["type"]}))
            if ja["condition"] != jb["condition"]:
                out.append(Finding(CAT_JOIN, SEV_CRITICAL, "msg_join_cond",
                                   {"table": tbl, "a": ja["condition"],
                                    "b": jb["condition"]}))

    # 3. WHERE filters.
    only_a, only_b = _diff_sets(a.filters, b.filters)
    for pred in only_a:
        out.append(Finding(CAT_FILTER, SEV_CRITICAL, "msg_filter_only",
                           {"side": "A", "pred": pred}))
    for pred in only_b:
        out.append(Finding(CAT_FILTER, SEV_CRITICAL, "msg_filter_only",
                           {"side": "B", "pred": pred}))

    # 4. Time range.
    only_a, only_b = _diff_sets(a.time_filters, b.time_filters)
    if only_a or only_b:
        out.append(Finding(CAT_TIME, SEV_RISK, "msg_time_differ",
                           {"a": "; ".join(a.time_filters) or "-",
                            "b": "; ".join(b.time_filters) or "-"}))

    # 5. Aggregation caliber.
    only_a, only_b = _diff_sets(a.aggregates, b.aggregates)
    if only_a or only_b:
        out.append(Finding(CAT_AGG, SEV_CRITICAL, "msg_agg_differ",
                           {"a": "; ".join(a.aggregates) or "-",
                            "b": "; ".join(b.aggregates) or "-"}))
    if a.group_by != b.group_by:
        out.append(Finding(CAT_AGG, SEV_RISK, "msg_group_differ",
                           {"a": ", ".join(a.group_by) or "-",
                            "b": ", ".join(b.group_by) or "-"}))

    # 6. Dedup mechanism.
    mech_a = _dedup_mech(a)
    mech_b = _dedup_mech(b)
    if mech_a != mech_b:
        out.append(Finding(CAT_DEDUP, SEV_CRITICAL, "msg_dedup_differ",
                           {"a": mech_a, "b": mech_b}))

    # 7. HAVING / LIMIT.
    if a.having != b.having:
        out.append(Finding(CAT_LIMIT, SEV_RISK, "msg_having_differ",
                           {"a": a.having or "-", "b": b.having or "-"}))
    if a.limit != b.limit:
        out.append(Finding(CAT_LIMIT, SEV_RISK, "msg_limit_differ",
                           {"a": a.limit or "-", "b": b.limit or "-"}))

    # 8. Output-only differences (after excluding aggregates already flagged).
    agg_all = set(a.aggregates) | set(b.aggregates)
    only_a, only_b = _diff_sets(
        [o for o in a.outputs if o not in agg_all],
        [o for o in b.outputs if o not in agg_all])
    if only_a or only_b:
        out.append(Finding(CAT_OUTPUT, SEV_INFO, "msg_output_differ",
                           {"only_a": ", ".join(only_a) or "-",
                            "only_b": ", ".join(only_b) or "-"}))

    out.sort(key=lambda f: _SEVERITY_ORDER[f.severity])
    return report


def _dedup_mech(prof: SqlProfile) -> str:
    if prof.row_number_dedup:
        return "row_number"
    if prof.distinct:
        return "distinct"
    if prof.group_by:
        return "group_by"
    return "none"
