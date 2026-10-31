"""Deterministic dimensional-model review of warehouse DDL.

metadata_quality judges how tables are declared (comments, naming,
types) and layer_check judges how lineage layers stack; this agent
judges the star schema itself.  Tables classify by name prefix —
``dim`` is a dimension, ``dwd``/``dws`` (and ``fact``) are facts, ``ods``
and ``stg`` are raw and mostly exempt — then:

* MR001 high — a dimension without a primary-key-shaped column
  (``id`` / ``*_id``): nothing for facts to join on;
* MR002 medium — a fact table without partitions: full rewrites and
  unprunable scans at fact volume;
* MR007 medium — a fact table without a single ``*_id`` column: it can
  reach no dimension;
* MR003 medium — descriptive dimension attributes (name/desc/addr/
  title/remark strings) living inside a fact: push them to a dimension;
* MR004 medium — the same non-key string attribute repeated across 2+
  fact tables: copies drift apart;
* MR005 low — an aggregate (``dws``) table with no measure-shaped
  numeric column;
* MR006 medium — a table wider than ``wide_limit`` columns.

DDL text in (schema_drift parser, nothing executed), graded report out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["ModelFinding", "ModelReport", "review_model"]

_ID = re.compile(r"(^id$|_id$)", re.IGNORECASE)
_DESCRIPTIVE = re.compile(r"(name|desc|describ|addr|title|remark|comment)",
                          re.IGNORECASE)
_MEASURE = re.compile(r"(amt|amount|cnt|count|qty|num$|sum|gmv|fee|price|"
                      r"total|rate|value)", re.IGNORECASE)
_STRINGY = re.compile(r"^(string|varchar|char|text)", re.IGNORECASE)
_NUMERIC = re.compile(r"^(bigint|int|integer|smallint|tinyint|decimal|"
                      r"double|float|numeric)", re.IGNORECASE)

SEVERITY = {"MR001": "high", "MR002": "medium", "MR003": "medium",
            "MR004": "medium", "MR005": "low", "MR006": "medium",
            "MR007": "medium"}

_FACT = ("dwd", "dws", "fact")
_DIM = ("dim",)
_RAW = ("ods", "stg", "tmp")


def _role(table: str) -> str:
    head = re.split(r"[._]", table, maxsplit=1)[0].lower()
    if head in _DIM:
        return "dim"
    if head in _FACT:
        return "fact"
    if head in _RAW:
        return "raw"
    return "other"


@dataclass
class ModelFinding:
    code: str           # MR001..MR007
    severity: str       # high | medium | low
    table: str
    detail: str = ""    # column(s) or value involved

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "table": self.table, "detail": self.detail}


@dataclass
class ModelReport:
    dialect: str
    tables_total: int = 0
    roles: dict[str, int] = field(default_factory=dict)
    findings: list[ModelFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"dialect": self.dialect,
                "tables_total": self.tables_total,
                "roles": dict(self.roles),
                "counts": self.counts(),
                "findings": [f.to_dict() for f in self.findings],
                "warnings": list(self.warnings)}


def review_model(sql_text: str, dialect: str = "hive",
                 wide_limit: int = 50) -> ModelReport:
    """CREATE TABLE DDL → star-schema findings, graded."""
    from seatunnel_agent.agents.data.schema_drift.differ import (
        parse_schema_script,
    )

    if not (sql_text or "").strip():
        raise ValueError("DDL must not be empty")
    if wide_limit < 1:
        raise ValueError("wide_limit must be positive")
    parsed, warnings = parse_schema_script(sql_text, dialect)
    if not parsed:
        raise ValueError("no CREATE TABLE found in the DDL"
                         + (f" ({warnings[0]})" if warnings else ""))

    report = ModelReport(dialect=dialect, tables_total=len(parsed),
                         warnings=list(warnings))

    def add(code: str, table: str, detail: str = "") -> None:
        report.findings.append(ModelFinding(
            code=code, severity=SEVERITY[code], table=table, detail=detail))

    attr_owners: dict[str, list[str]] = {}   # fact attribute -> fact tables
    for name in sorted(parsed):
        schema = parsed[name]
        role = _role(name)
        report.roles[role] = report.roles.get(role, 0) + 1
        data_cols = [c for c in schema.columns.values()
                     if not c.is_partition]
        id_cols = [c.name for c in data_cols if _ID.search(c.name)]

        if role == "dim" and not id_cols:
            add("MR001", name)
        if role == "fact":
            if not schema.partition_cols:
                add("MR002", name)
            if not id_cols:
                add("MR007", name)
            leaked = [c.name for c in data_cols
                      if _STRINGY.match(c.col_type or "")
                      and _DESCRIPTIVE.search(c.name)
                      and not _ID.search(c.name)]
            if leaked:
                add("MR003", name, ", ".join(leaked[:6]))
            for c in data_cols:
                if (_STRINGY.match(c.col_type or "")
                        and not _ID.search(c.name)):
                    attr_owners.setdefault(c.name, []).append(name)
        if role == "fact" and name.split(".", 1)[0].lower() == "dws":
            measures = [c.name for c in data_cols
                        if _NUMERIC.match(c.col_type or "")
                        and _MEASURE.search(c.name)]
            if not measures:
                add("MR005", name)
        if len(data_cols) > wide_limit:
            add("MR006", name, str(len(data_cols)))

    for attr, owners in sorted(attr_owners.items()):
        if len(owners) >= 2:
            add("MR004", ", ".join(owners), attr)
    return report
