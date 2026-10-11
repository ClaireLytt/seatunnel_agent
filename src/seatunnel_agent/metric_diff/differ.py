# -*- coding: utf-8 -*-
"""Deterministic metric-definition comparison over column lineage.

A "definition" of output column ``c`` in table ``t`` is the set of lineage
expressions feeding ``t.c``. Definitions across all tables are grouped by
the bare column name; a group conflicts when canonical expressions differ.

Canonicalization: trailing ``AS alias`` stripped, table qualifiers dropped,
sqlglot round-trip (or a regex fallback when the fragment does not parse),
``COUNT(1)`` folded to ``COUNT(*)``, case-insensitive compare.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..data_lineage.graph import LineageGraph

SEVERITIES = ("high", "medium")
_SEV_RANK = {"medium": 1, "high": 2}

_AS_TAIL_RE = re.compile(r"\s+AS\s+[`\"']?\w+[`\"']?\s*$", re.IGNORECASE)
_QUALIFIER_RE = re.compile(r"\b\w+\.(?=\w)")
_COUNT_ONE_RE = re.compile(r"\bCOUNT\(\s*1\s*\)", re.IGNORECASE)


def canonical_expr(expression: str, dialect: str = "hive") -> str:
    """Comparable form of a lineage expression; '' for a missing one."""
    text = _AS_TAIL_RE.sub("", (expression or "").strip())
    if not text:
        return ""
    try:
        import sqlglot
        from sqlglot import exp

        from ..data_lineage.sqlglot_lineage import resolve_sqlglot_dialect

        node = sqlglot.parse_one(text, read=resolve_sqlglot_dialect(dialect))
        for col in node.find_all(exp.Column):
            col.set("table", None)
            col.set("db", None)
            col.set("catalog", None)
        text = node.sql()
    except Exception:  # noqa: BLE001 — fall back to text normalization
        text = _QUALIFIER_RE.sub("", text)
    text = _COUNT_ONE_RE.sub("COUNT(*)", text)
    return re.sub(r"\s+", " ", text).strip().upper()


@dataclass
class MetricDef:
    table: str
    column: str
    expression: str            # raw lineage expression
    canonical: str
    sources: list[str]         # src table.column(s) feeding it
    origins: list[str]         # files that produce the table
    computed: bool             # expression beyond a bare column copy

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "column": self.column,
                "expression": self.expression, "canonical": self.canonical,
                "sources": list(self.sources), "origins": list(self.origins),
                "computed": self.computed}


@dataclass
class MetricConflict:
    name: str
    severity: str              # high | medium
    kind: str                  # expr_conflict | source_conflict
    defs: list[MetricDef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "severity": self.severity,
                "kind": self.kind,
                "definitions": [d.to_dict() for d in self.defs]}


@dataclass
class MetricReport:
    root: str
    dialect: str
    conflicts: list[MetricConflict] = field(default_factory=list)
    metrics_checked: int = 0
    consistent: int = 0
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {level: 0 for level in SEVERITIES}
        for c in self.conflicts:
            out[c.severity] += 1
        out["total"] = len(self.conflicts)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {"root": self.root, "dialect": self.dialect,
                "metrics_checked": self.metrics_checked,
                "consistent": self.consistent,
                "counts": self.counts(),
                "conflicts": [c.to_dict() for c in self.conflicts],
                "warnings": list(self.warnings)}


def _is_computed(expression: str, dst_column: str, src_column: str) -> bool:
    """True when the expression is more than copying one column through."""
    text = _AS_TAIL_RE.sub("", (expression or "").strip())
    if not text:
        return False
    bare = _QUALIFIER_RE.sub("", text).strip().lower()
    return bare not in (dst_column.lower(), src_column.lower())


def _definitions(graph: LineageGraph, dialect: str) -> dict[str, list[MetricDef]]:
    """bare column name → its definitions across every producing table."""
    by_dst: dict[tuple[str, str], list] = {}
    for (table, column), edges in graph.column_up.items():
        by_dst.setdefault((table, column), []).extend(edges)

    metrics: dict[str, list[MetricDef]] = {}
    for (table, column), edges in sorted(by_dst.items()):
        node = graph.get(table)
        origins = sorted(node.origins) if node else []
        sources = sorted({f"{e.src_table}.{e.src_column}" for e in edges})
        # one dst column may be fed by several edges (e.g. CASE over two
        # columns): canonicalize the combined definition
        exprs = sorted({(e.expression or e.src_column) for e in edges})
        raw = " | ".join(exprs)
        canonical = " | ".join(
            canonical_expr(x, dialect) or x.upper() for x in exprs)
        computed = any(
            _is_computed(e.expression, column, e.src_column) for e in edges)
        metrics.setdefault(column, []).append(MetricDef(
            table=table, column=column, expression=raw,
            canonical=canonical, sources=sources, origins=origins,
            computed=computed))
    return metrics


def check_graph(graph: LineageGraph, root: str = "", dialect: str = "hive",
                warnings: list[str] | None = None) -> MetricReport:
    report = MetricReport(root=root, dialect=dialect,
                          warnings=list(warnings or []))
    metrics = _definitions(graph, dialect)
    report.metrics_checked = len(metrics)
    for name, defs in sorted(metrics.items()):
        if len(defs) < 2:
            report.consistent += 1
            continue
        canonicals = {d.canonical for d in defs}
        if len(canonicals) < 2:
            report.consistent += 1
            continue
        if any(d.computed for d in defs):
            # at least one side computes — differing formulas = caliber drift
            report.conflicts.append(MetricConflict(
                name=name, severity="high", kind="expr_conflict", defs=defs))
            continue
        base_sources = {s.rpartition(".")[2] for d in defs
                        for s in d.sources}
        if len(base_sources) > 1:
            # plain copies, but from differently-named source columns
            report.conflicts.append(MetricConflict(
                name=name, severity="medium", kind="source_conflict",
                defs=defs))
        else:
            report.consistent += 1
    report.conflicts.sort(
        key=lambda c: (-_SEV_RANK[c.severity], c.name))
    return report


def check_sql_dir(directory: str, dialect: str = "hive") -> MetricReport:
    from ..data_lineage.loaders import from_sql_dir

    graph, warnings = from_sql_dir(directory, dialect=dialect)
    return check_graph(graph, root=str(directory), dialect=dialect,
                       warnings=warnings)
