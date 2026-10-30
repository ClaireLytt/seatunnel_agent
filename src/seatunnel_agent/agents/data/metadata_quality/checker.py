"""Deterministic DDL conventions checker."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LAYERS = ("ods", "dwd", "dws", "ads", "dim")

_MONEY_RE = re.compile(
    r"(^|_)(amount|amt|price|fee|salary|money|cost|income|pay)(_|$)")
_FLOATY = ("float", "double")
_DATEISH_RE = re.compile(r"(^|_)(date|day|time|dt)(_|$)")


@dataclass
class MetaFinding:
    kind: str            # missing_comment | layer_naming | money_float |
                         # date_string | money_string | unpartitioned_fact
    severity: str        # high | medium | low
    table: str
    column: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity,
                "table": self.table, "column": self.column,
                "detail": self.detail}


@dataclass
class TableCoverage:
    table: str
    total: int
    commented: int

    @property
    def pct(self) -> int:
        return round(100 * self.commented / self.total) if self.total else 100

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "total": self.total,
                "commented": self.commented, "pct": self.pct}


@dataclass
class MetaQualityReport:
    root: str
    dialect: str
    tables_checked: int = 0
    findings: list[MetaFinding] = field(default_factory=list)
    coverage: list[TableCoverage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        sev = {"high": 0, "medium": 0, "low": 0}
        for f in self.findings:
            sev[f.severity] += 1
        return {**sev, "total": len(self.findings)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "dialect": self.dialect,
            "tables_checked": self.tables_checked,
            "counts": self.counts(),
            "coverage": [c.to_dict() for c in self.coverage],
            "findings": [f.to_dict() for f in self.findings],
            "warnings": list(self.warnings),
        }


def _layer_of(database: str) -> str | None:
    base = database.split(".")[-1].lower()
    for layer in LAYERS:
        if base == layer or base.startswith(layer + "_"):
            return layer
    return None


def _check_text(sql_text: str, dialect: str, root: str) -> MetaQualityReport:
    from seatunnel_agent.agents.data.schema_drift.differ import (
        parse_schema_script,
    )

    tables, warnings = parse_schema_script(sql_text, dialect)
    report = MetaQualityReport(root=root, dialect=dialect,
                               tables_checked=len(tables),
                               warnings=list(warnings))

    for name, schema in sorted(tables.items()):
        cols = list(schema.columns.values())
        commented = sum(1 for c in cols if (c.comment or "").strip())
        report.coverage.append(TableCoverage(
            table=name, total=len(cols), commented=commented))
        for c in cols:
            if not (c.comment or "").strip():
                report.findings.append(MetaFinding(
                    kind="missing_comment", severity="low",
                    table=name, column=c.name,
                    detail="no COMMENT on column"))
            lname = c.name.lower()
            ltype = (c.col_type or "").lower()
            if _MONEY_RE.search(lname) and any(
                    ltype.startswith(t) for t in _FLOATY):
                report.findings.append(MetaFinding(
                    kind="money_float", severity="high",
                    table=name, column=c.name,
                    detail=f"money-named column typed {c.col_type}; "
                           "binary floats lose cents - use DECIMAL"))
            if (_DATEISH_RE.search(lname) and not c.is_partition
                    and ltype == "string"):
                report.findings.append(MetaFinding(
                    kind="date_string", severity="medium",
                    table=name, column=c.name,
                    detail="date-named column typed bare STRING; "
                           "prefer DATE/TIMESTAMP or document the format"))
            if _MONEY_RE.search(lname) and ltype == "string":
                report.findings.append(MetaFinding(
                    kind="money_string", severity="medium",
                    table=name, column=c.name,
                    detail="money-named column typed STRING; arithmetic "
                           "silently casts - use DECIMAL"))

        # layer naming: only the unambiguous smell is flagged — a table whose
        # name claims a DIFFERENT layer than the database it lives in
        # (dwd.ods_xxx). Unprefixed tables inside a layered database are a
        # legitimate style and stay silent.
        db, _, tbl = name.rpartition(".")
        db_layer = _layer_of(db) if db else None
        tbl_layer = next((la for la in LAYERS
                          if tbl.lower().startswith(la + "_")), None)
        if db_layer and tbl_layer and tbl_layer != db_layer:
            report.findings.append(MetaFinding(
                kind="layer_naming", severity="medium",
                table=name,
                detail=f"table prefix claims layer '{tbl_layer}' but lives "
                       f"in layer '{db_layer}'"))

        # fact-layer tables (dwd/dws) without a partition spec: full scans
        # and no retention story. dim/ods/ads stay silent - small dims and
        # serving tables are legitimately unpartitioned.
        fact_layer = db_layer or tbl_layer
        if fact_layer in ("dwd", "dws") and not schema.partition_cols:
            report.findings.append(MetaFinding(
                kind="unpartitioned_fact", severity="medium",
                table=name,
                detail=f"'{fact_layer}' table has no PARTITIONED BY; "
                       "fact tables need a partition and retention story"))

    return report


def check_sql_text(sql_text: str, dialect: str = "hive",
                   root: str = "<inline>") -> MetaQualityReport:
    return _check_text(sql_text, dialect, root)


def check_files(paths: list[Path] | list[str], dialect: str = "hive",
                root: str = "") -> MetaQualityReport:
    resolved = [Path(p) for p in paths]
    text = "\n;\n".join(p.read_text(encoding="utf-8") for p in resolved)
    return _check_text(text, dialect, root or str(resolved[0]))


def check_dir(directory: str | Path, dialect: str = "hive",
              ) -> MetaQualityReport:
    base = Path(directory)
    files = sorted(base.rglob("*.sql"))
    text = "\n;\n".join(p.read_text(encoding="utf-8") for p in files)
    return _check_text(text, dialect, str(base))
