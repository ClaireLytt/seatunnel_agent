"""Deterministic column-level usage inventory over a query workload.

asset_value scores tables; this agent descends to the columns.  Paste
the tables' CREATE TABLE DDL (schema_drift parser reused) plus a
workload of query SQL (the day's scheduler scripts, a log export) and
every DDL column gets its reference count across SELECT / WHERE / JOIN /
GROUP BY, with alias resolution per statement:

* FU001 medium — a DDL table the workload never reads: an offboarding
  candidate;
* FU002 low — columns never referenced while their table is read:
  trimming candidates (storage and scan width);
* FU003 low — ``SELECT *`` reads of a table: column-level stats go
  blind there, and the count is reported.

Unqualified columns attribute to the statement's only source table when
unambiguous, and are skipped otherwise (never guessed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["FieldUsageReport", "TableUsage", "UsageFinding",
           "analyze_usage"]


@dataclass
class TableUsage:
    table: str
    reads: int = 0
    star_reads: int = 0
    columns: dict[str, int] = field(default_factory=dict)  # name -> refs
    unused: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "reads": self.reads,
                "star_reads": self.star_reads,
                "columns": dict(self.columns),
                "unused": list(self.unused)}


@dataclass
class UsageFinding:
    code: str            # FU001..FU003
    severity: str        # medium | low
    table: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "table": self.table, "detail": self.detail}


@dataclass
class FieldUsageReport:
    queries_total: int = 0
    tables: list[TableUsage] = field(default_factory=list)
    findings: list[UsageFinding] = field(default_factory=list)
    top_columns: list[tuple[str, int]] = field(default_factory=list)
    unresolved_refs: int = 0
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"queries_total": self.queries_total,
                "counts": self.counts(),
                "tables": [t.to_dict() for t in self.tables],
                "findings": [f.to_dict() for f in self.findings],
                "top_columns": [{"column": c, "refs": n}
                                for c, n in self.top_columns],
                "unresolved_refs": self.unresolved_refs,
                "warnings": list(self.warnings)}


def _table_name(t) -> str:
    parts = [p for p in (t.catalog, t.db, t.name) if p]
    return ".".join(parts).lower()


def analyze_usage(ddl_text: str, queries_text: str,
                  dialect: str = "hive") -> FieldUsageReport:
    """DDL + query workload → per-column reference counts, graded."""
    import sqlglot
    from sqlglot import exp

    from seatunnel_agent.agents.data.data_lineage.sqlglot_lineage import (
        resolve_sqlglot_dialect,
    )
    from seatunnel_agent.agents.data.schema_drift.differ import (
        parse_schema_script,
    )

    schemas, warnings = parse_schema_script(ddl_text, dialect)
    if not schemas:
        raise ValueError("no CREATE TABLE found in the DDL"
                         + (f" ({warnings[0]})" if warnings else ""))
    if not (queries_text or "").strip():
        raise ValueError("the query workload must not be empty")

    read = resolve_sqlglot_dialect(dialect)
    try:
        statements = sqlglot.parse(queries_text, read=read)
    except sqlglot.errors.ParseError as exc:
        raise ValueError(f"queries: cannot parse ({str(exc)[:200]})")

    usage = {name: TableUsage(table=name,
                              columns={c: 0 for c, col in
                                       schemas[name].columns.items()})
             for name in schemas}
    report = FieldUsageReport(warnings=list(warnings))

    for tree in statements:
        if tree is None:
            continue
        report.queries_total += 1
        for select in tree.find_all(exp.Select):
            # alias -> real table map, scoped to this SELECT
            alias_map: dict[str, str] = {}
            sources: list[str] = []
            for t in select.find_all(exp.Table):
                real = _table_name(t)
                if real not in usage:
                    continue
                sources.append(real)
                alias_map[(t.alias or t.name).lower()] = real
                alias_map[real] = real
            for real in set(sources):
                usage[real].reads += 1
            for star in select.find_all(exp.Star):
                owner = None
                parent = star.parent
                if isinstance(parent, exp.Column) and parent.table:
                    owner = alias_map.get(parent.table.lower())
                elif len(set(sources)) == 1:
                    owner = sources[0]
                if owner:
                    usage[owner].star_reads += 1
            for col in select.find_all(exp.Column):
                if isinstance(col.this, exp.Star):
                    continue
                name = col.name.lower()
                if col.table:
                    real = alias_map.get(col.table.lower())
                    if real is None:
                        report.unresolved_refs += 1
                        continue
                    if name in usage[real].columns:
                        usage[real].columns[name] += 1
                    continue
                owners = [s for s in set(sources)
                          if name in usage[s].columns]
                if len(owners) == 1:
                    usage[owners[0]].columns[name] += 1
                elif owners:
                    report.unresolved_refs += 1

    for name in sorted(usage):
        tu = usage[name]
        tu.unused = sorted(c for c, n in tu.columns.items() if n == 0)
        report.tables.append(tu)
        if tu.reads == 0:
            report.findings.append(UsageFinding(
                code="FU001", severity="medium", table=name))
        elif tu.unused and not tu.star_reads:
            report.findings.append(UsageFinding(
                code="FU002", severity="low", table=name,
                detail=", ".join(tu.unused[:8])
                + ("…" if len(tu.unused) > 8 else "")))
        if tu.star_reads:
            report.findings.append(UsageFinding(
                code="FU003", severity="low", table=name,
                detail=str(tu.star_reads)))

    all_cols = [(f"{t.table}.{c}", n) for t in report.tables
                for c, n in t.columns.items() if n > 0]
    report.top_columns = sorted(all_cols, key=lambda kv: -kv[1])[:10]
    order = {"medium": 0, "low": 1}
    report.findings.sort(key=lambda f: (order[f.severity], f.code, f.table))
    report.tables.sort(key=lambda t: (t.reads, t.table))
    return report
