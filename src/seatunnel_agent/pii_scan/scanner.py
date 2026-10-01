# -*- coding: utf-8 -*-
"""Deterministic PII scan core.

Column inventory comes from two sources merged together:

1. ``CREATE TABLE`` statements in the scanned SQL (column name, type and
   COMMENT — the comment is what the Chinese-keyword rules match against);
2. column-level lineage edges (columns that only appear in INSERT/SELECT).

Every rule hit is then pushed through ``LineageGraph.impact_of_column`` to
report the downstream spread, with each propagation edge classified as
masked / unmasked by its expression (``rules.expression_is_masked``).
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..data_lineage.graph import LineageGraph, norm_table
from ..data_lineage.loaders import from_sql_files
from .rules import DEFAULT_RULES, PiiRule, expression_is_masked

_SEV_RANK = {"low": 1, "medium": 2, "high": 3}
_RANK_SEV = {v: k for k, v in _SEV_RANK.items()}
SPREAD_DEPTH = 5

# Column names that already look masked (phone_md5, id_card_hash, ...) are
# demoted to low severity / low confidence — the raw value is gone.
import re as _re

_MASKED_NAME_RE = _re.compile(
    r"(^|_)(md5|hash|hashed|sha\d*|enc|encrypted|mask|masked|cipher)(_|$)")


@dataclass
class ColumnRef:
    table: str
    column: str
    col_type: str = ""
    comment: str = ""
    origin: str = ""        # "ddl" | "lineage"
    is_partition: bool = False


@dataclass
class SpreadEdge:
    src: str                # table.column
    dst: str
    expression: str
    masked: bool

    def to_dict(self) -> dict[str, Any]:
        return {"src": self.src, "dst": self.dst,
                "expression": self.expression, "masked": self.masked}


@dataclass
class PiiFinding:
    table: str
    column: str
    category: str
    severity: str           # after spread escalation
    base_severity: str      # the rule's own severity
    confidence: str         # high | low
    matched_by: str         # name | comment | name+comment
    evidence: str           # pattern / keyword that hit
    col_type: str = ""
    comment: str = ""
    impacted: list[str] = field(default_factory=list)
    spread_edges: list[SpreadEdge] = field(default_factory=list)

    @property
    def unmasked_edges(self) -> list[SpreadEdge]:
        return [e for e in self.spread_edges if not e.masked]

    @property
    def masked_edges(self) -> list[SpreadEdge]:
        return [e for e in self.spread_edges if e.masked]

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "column": self.column,
            "category": self.category,
            "severity": self.severity,
            "base_severity": self.base_severity,
            "confidence": self.confidence,
            "matched_by": self.matched_by,
            "evidence": self.evidence,
            "col_type": self.col_type,
            "comment": self.comment,
            "impacted": list(self.impacted),
            "spread_edges": [e.to_dict() for e in self.spread_edges],
            "unmasked_spread": len(self.unmasked_edges),
        }


@dataclass
class PiiReport:
    root: str
    dialect: str
    findings: list[PiiFinding] = field(default_factory=list)
    tables_scanned: int = 0
    columns_scanned: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def high(self) -> list[PiiFinding]:
        return [f for f in self.findings if f.severity == "high"]

    @property
    def medium(self) -> list[PiiFinding]:
        return [f for f in self.findings if f.severity == "medium"]

    @property
    def low(self) -> list[PiiFinding]:
        return [f for f in self.findings if f.severity == "low"]

    def counts(self) -> dict[str, int]:
        return {"high": len(self.high), "medium": len(self.medium),
                "low": len(self.low), "total": len(self.findings)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "dialect": self.dialect,
            "tables_scanned": self.tables_scanned,
            "columns_scanned": self.columns_scanned,
            "counts": self.counts(),
            "findings": [f.to_dict() for f in self.findings],
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# column inventory
# ---------------------------------------------------------------------------

def collect_columns_from_ddl(sql_text: str, dialect: str = "hive",
                             ) -> tuple[list[ColumnRef], list[str]]:
    """Columns (name/type/comment) from every CREATE TABLE in *sql_text*."""
    import sqlglot
    from sqlglot import exp

    from ..data_lineage.sqlglot_lineage import resolve_sqlglot_dialect

    read = resolve_sqlglot_dialect(dialect)
    refs: list[ColumnRef] = []
    warnings: list[str] = []
    try:
        statements = sqlglot.parse(sql_text, read=read)
    except sqlglot.errors.ParseError as exc:
        return [], [f"DDL 解析失败: {exc}"]
    for tree in statements:
        if not isinstance(tree, exp.Create):
            continue
        if (tree.args.get("kind") or "").upper() != "TABLE":
            continue
        table_expr = tree.find(exp.Table)
        if table_expr is None:
            continue
        parts = [p for p in (table_expr.catalog, table_expr.db,
                             table_expr.name) if p]
        table = norm_table(".".join(parts))
        part_cols: set[str] = set()
        prop = tree.find(exp.PartitionedByProperty)
        if prop is not None:
            part_cols = {cd.name.lower() for cd in
                         prop.find_all(exp.ColumnDef)}
        for cd in tree.find_all(exp.ColumnDef):
            if not cd.name:
                continue
            kind = cd.args.get("kind")
            try:
                col_type = kind.sql(dialect=read) if kind is not None else ""
            except Exception:  # noqa: BLE001 — type rendering is best-effort
                col_type = str(kind or "")
            comment = ""
            for c in cd.args.get("constraints") or []:
                if isinstance(c.kind, exp.CommentColumnConstraint):
                    comment = c.kind.this.name
            refs.append(ColumnRef(
                table=table, column=cd.name.lower(), col_type=col_type,
                comment=comment, origin="ddl",
                is_partition=cd.name.lower() in part_cols))
    return refs, warnings


def _columns_from_graph(graph: LineageGraph) -> list[ColumnRef]:
    seen: set[tuple[str, str]] = set()
    refs: list[ColumnRef] = []
    for key in list(graph.column_down) + list(graph.column_up):
        if key in seen:
            continue
        seen.add(key)
        refs.append(ColumnRef(table=key[0], column=key[1], origin="lineage"))
    return refs


def _merge_columns(ddl: Iterable[ColumnRef],
                   lineage: Iterable[ColumnRef]) -> list[ColumnRef]:
    by_key: dict[tuple[str, str], ColumnRef] = {}
    for ref in ddl:
        by_key[(ref.table, ref.column)] = ref
    for ref in lineage:
        by_key.setdefault((ref.table, ref.column), ref)
    return sorted(by_key.values(), key=lambda r: (r.table, r.column))


# ---------------------------------------------------------------------------
# rule matching + spread
# ---------------------------------------------------------------------------

def _match_rules(ref: ColumnRef, rules: Iterable[PiiRule],
                 ) -> tuple[PiiRule, str, str, str] | None:
    """Best (rule, confidence, matched_by, evidence) for one column."""
    best: tuple[int, int, PiiRule, str, str, str] | None = None
    name = ref.column.lower()
    comment = ref.comment or ""
    for rule in rules:
        strong, weak = rule.compiled()

        def _hit_text(patterns: list) -> str:
            for p in patterns:
                m = p.search(name)
                if m:
                    return m.group(0).strip("_") or name
            return ""

        matched_name = _hit_text(strong)
        matched_weak = "" if matched_name else _hit_text(weak)
        matched_kw = next(
            (k for k in rule.comment_keywords if k and k in comment), "")
        if not (matched_name or matched_weak or matched_kw):
            continue
        if matched_name and matched_kw:
            matched_by, evidence, conf = ("name+comment",
                                          f"{matched_name} + {matched_kw}",
                                          "high")
        elif matched_name:
            matched_by, evidence, conf = "name", matched_name, "high"
        elif matched_kw:
            matched_by, evidence, conf = "comment", matched_kw, "high"
        else:
            matched_by, evidence, conf = "name", matched_weak, "low"
        score = (_SEV_RANK[rule.severity], 1 if conf == "high" else 0)
        if best is None or score > (best[0], best[1]):
            best = (*score, rule, conf, matched_by, evidence)
    if best is None:
        return None
    return best[2], best[3], best[4], best[5]


def _spread(graph: LineageGraph, table: str, column: str,
            ) -> tuple[list[str], list[SpreadEdge]]:
    result = graph.impact_of_column(table, column, depth=SPREAD_DEPTH)
    edges = [SpreadEdge(
        src=f"{e.src_table}.{e.src_column}",
        dst=f"{e.dst_table}.{e.dst_column}",
        expression=e.expression,
        masked=expression_is_masked(e.expression),
    ) for e in result.edges]
    return list(result.impacted), edges


def _escalate(base: str, unmasked_spread: bool, confidence: str) -> str:
    """Spread without masking bumps severity one level; a weak name-only
    match never rises above its base level."""
    if not unmasked_spread or confidence == "low":
        return base
    return _RANK_SEV[min(3, _SEV_RANK[base] + 1)]


def _scan(graph: LineageGraph, ddl_cols: list[ColumnRef], root: str,
          dialect: str, warnings: list[str],
          rules: Iterable[PiiRule] | None = None) -> PiiReport:
    rules = list(rules) if rules else list(DEFAULT_RULES)
    columns = _merge_columns(ddl_cols, _columns_from_graph(graph))
    report = PiiReport(root=root, dialect=dialect, warnings=list(warnings))
    report.columns_scanned = len(columns)
    report.tables_scanned = len({c.table for c in columns})
    for ref in columns:
        hit = _match_rules(ref, rules)
        if hit is None:
            continue
        rule, confidence, matched_by, evidence = hit
        base_severity = rule.severity
        if _MASKED_NAME_RE.search(ref.column):
            # phone_md5 / id_card_hash — the stored value is already masked
            base_severity, confidence = "low", "low"
        impacted, edges = _spread(graph, ref.table, ref.column)
        unmasked = any(not e.masked for e in edges)
        finding = PiiFinding(
            table=ref.table, column=ref.column, category=rule.category,
            severity=_escalate(base_severity, unmasked, confidence),
            base_severity=base_severity, confidence=confidence,
            matched_by=matched_by, evidence=evidence,
            col_type=ref.col_type, comment=ref.comment,
            impacted=impacted, spread_edges=edges)
        report.findings.append(finding)
    report.findings.sort(
        key=lambda f: (-_SEV_RANK[f.severity], f.table, f.column))
    return report


# ---------------------------------------------------------------------------
# entry points
# ---------------------------------------------------------------------------

def scan_files(paths: list[Path] | list[str], dialect: str = "hive",
               rules: Iterable[PiiRule] | None = None,
               root: str = "", cache_base: str | Path = "logs") -> PiiReport:
    graph, warnings = from_sql_files(
        [Path(p) for p in paths], dialect=dialect, cache_base=cache_base)
    ddl_cols: list[ColumnRef] = []
    for raw in paths:
        try:
            text = Path(raw).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            warnings.append(f"无法读取 {raw}: {exc}")
            continue
        cols, warn = collect_columns_from_ddl(text, dialect)
        ddl_cols.extend(cols)
        warnings.extend(f"{raw}: {w}" for w in warn)
    return _scan(graph, ddl_cols, root or f"{len(list(paths))} files",
                 dialect, warnings, rules)


def scan_dir(directory: str | Path, dialect: str = "hive",
             rules: Iterable[PiiRule] | None = None) -> PiiReport:
    from ..sql_review.runner import collect_sql_files

    files = collect_sql_files(directory)
    if not files:
        return PiiReport(root=str(directory), dialect=dialect,
                         warnings=[f"目录 {directory} 下没有找到 *.sql 文件"])
    return scan_files(files, dialect=dialect, rules=rules,
                      root=str(directory))


def scan_sql_text(sql_text: str, dialect: str = "hive",
                  rules: Iterable[PiiRule] | None = None) -> PiiReport:
    """Scan a pasted script; temp files keep the lineage cache clean."""
    with tempfile.TemporaryDirectory(prefix="pii_scan_") as td:
        path = Path(td) / "inline.sql"
        path.write_text(sql_text, encoding="utf-8")
        return scan_files([path], dialect=dialect, rules=rules,
                          root="<inline>", cache_base=td)
