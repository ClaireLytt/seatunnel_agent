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

from ..data_lineage.graph import LineageGraph
from ..data_lineage.loaders import from_sql_files
from .rules import (DEFAULT_RULES, PiiRule, expression_is_masked,
                    match_column)

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
    """Columns (name/type/comment) from every CREATE TABLE in *sql_text*.

    Thin adapter over ``schema_drift.differ.parse_schema_script`` — one
    sqlglot DDL walker for the whole suite."""
    from ..schema_drift.differ import parse_schema_script

    tables, warnings = parse_schema_script(sql_text, dialect)
    refs = [
        ColumnRef(table=schema.name, column=col.name,
                  col_type=col.col_type, comment=col.comment,
                  origin="ddl", is_partition=col.is_partition)
        for schema in tables.values()
        for col in schema.columns.values()
    ]
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
    return match_column(ref.column, ref.comment or "", rules)


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
