"""Deterministic data-contract checker.

A contract is a YAML document declaring what a team promises about its
tables; the checker compares those promises against the actual DDL
(parsed with the schema_drift parser — no database, nothing executed).

Contract shape::

    tables:
      - name: dwd.orders
        columns:                      # declared columns must exist
          - name: order_id
            type: bigint              # optional; checked when present
            comment: true             # optional; this column must be commented
        require_comments: true        # optional; every column needs a comment
        partitioned_by: [dt]          # optional; exact partition column list
        allow_extra_columns: true     # default true; false flags extras

Unlike schema_drift (two DDL snapshots against each other) this checks one
DDL snapshot against a declared expectation, so it gates "did we break the
promise" rather than "did anything change".
"""

from __future__ import annotations

from seatunnel_agent.common.severity import severity_counts

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# finding kind -> severity: breaking a declared promise is high; shape
# drift around the promise (partitions, comments, extras) grades down
KIND_SEVERITY = {
    "missing_table": "high",
    "missing_column": "high",
    "type_mismatch": "high",
    "partition_mismatch": "medium",
    "missing_comment": "low",
    "extra_column": "low",
}


@dataclass
class ColumnContract:
    name: str
    col_type: str = ""        # "" = any type
    comment: bool = False     # True = a COMMENT is required


@dataclass
class TableContract:
    name: str
    columns: list[ColumnContract] = field(default_factory=list)
    require_comments: bool = False
    partitioned_by: list[str] | None = None   # None = not declared
    allow_extra_columns: bool = True


@dataclass
class ContractFinding:
    kind: str            # one of KIND_SEVERITY
    severity: str        # high | medium | low
    table: str
    column: str = ""
    expected: str = ""
    actual: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity,
                "table": self.table, "column": self.column,
                "expected": self.expected, "actual": self.actual}


@dataclass
class ContractReport:
    root: str
    dialect: str
    tables_declared: int = 0
    tables_checked: int = 0
    findings: list[ContractFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "dialect": self.dialect,
            "tables_declared": self.tables_declared,
            "tables_checked": self.tables_checked,
            "counts": self.counts(),
            "findings": [f.to_dict() for f in self.findings],
            "warnings": list(self.warnings),
        }


def parse_contract(contract_text: str) -> list[TableContract]:
    """YAML contract text → table contracts; raises ValueError on shape."""
    import yaml

    try:
        raw = yaml.safe_load(contract_text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"contract is not valid YAML: {exc}")
    items = raw.get("tables") if isinstance(raw, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError("contract must declare a top-level tables: [...] list")
    out: list[TableContract] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict) or not str(item.get("name", "")).strip():
            raise ValueError(f"tables[{i}]: every table needs a name")
        cols: list[ColumnContract] = []
        for j, c in enumerate(item.get("columns") or []):
            if isinstance(c, str):
                cols.append(ColumnContract(name=c))
                continue
            if not isinstance(c, dict) or not str(c.get("name", "")).strip():
                raise ValueError(
                    f"tables[{i}].columns[{j}]: every column needs a name")
            cols.append(ColumnContract(
                name=str(c["name"]),
                col_type=str(c.get("type") or ""),
                comment=bool(c.get("comment", False))))
        part = item.get("partitioned_by")
        if part is not None and not isinstance(part, list):
            raise ValueError(f"tables[{i}].partitioned_by must be a list")
        out.append(TableContract(
            name=str(item["name"]),
            columns=cols,
            require_comments=bool(item.get("require_comments", False)),
            partitioned_by=[str(p) for p in part] if part is not None else None,
            allow_extra_columns=bool(item.get("allow_extra_columns", True))))
    return out


def _norm_type(t: str) -> str:
    # whitespace-insensitive: DECIMAL(16, 2) == decimal(16,2)
    return "".join((t or "").lower().split())


def _type_matches(expected: str, actual: str) -> bool:
    """`decimal` in the contract accepts `DECIMAL(16,2)`; a parameterized
    contract type must match exactly (both normalized)."""
    exp, act = _norm_type(expected), _norm_type(actual)
    if "(" in exp:
        return exp == act
    return act == exp or act.startswith(exp + "(")


def _check_text(sql_text: str, contract_text: str, dialect: str,
                root: str) -> ContractReport:
    from seatunnel_agent.agents.data.schema_drift.differ import (
        parse_schema_script,
    )

    contracts = parse_contract(contract_text)
    tables, warnings = parse_schema_script(sql_text, dialect)
    by_name = {name.lower(): schema for name, schema in tables.items()}
    report = ContractReport(root=root, dialect=dialect,
                            tables_declared=len(contracts),
                            warnings=list(warnings))

    def add(kind: str, table: str, column: str = "",
            expected: str = "", actual: str = "") -> None:
        report.findings.append(ContractFinding(
            kind=kind, severity=KIND_SEVERITY[kind], table=table,
            column=column, expected=expected, actual=actual))

    for tc in contracts:
        schema = by_name.get(tc.name.lower())
        if schema is None:
            add("missing_table", tc.name, expected="declared in contract",
                actual="not found in DDL")
            continue
        report.tables_checked += 1
        actual_cols = {c.name.lower(): c for c in schema.columns.values()}
        declared = {c.name.lower() for c in tc.columns}
        for cc in tc.columns:
            col = actual_cols.get(cc.name.lower())
            if col is None:
                add("missing_column", tc.name, cc.name,
                    expected=cc.col_type or "any type", actual="absent")
                continue
            if cc.col_type and not _type_matches(cc.col_type, col.col_type):
                add("type_mismatch", tc.name, cc.name,
                    expected=cc.col_type, actual=col.col_type)
            if cc.comment and not (col.comment or "").strip():
                add("missing_comment", tc.name, cc.name,
                    expected="COMMENT required", actual="no comment")
        if tc.require_comments:
            for col in schema.columns.values():
                if (col.name.lower() not in declared
                        and not (col.comment or "").strip()):
                    add("missing_comment", tc.name, col.name,
                        expected="COMMENT required", actual="no comment")
        if tc.partitioned_by is not None:
            want = [p.lower() for p in tc.partitioned_by]
            got = [p.lower() for p in schema.partition_cols]
            if want != got:
                add("partition_mismatch", tc.name,
                    expected=", ".join(tc.partitioned_by) or "(none)",
                    actual=", ".join(schema.partition_cols) or "(none)")
        if not tc.allow_extra_columns:
            for col in schema.columns.values():
                if col.name.lower() not in declared and not col.is_partition:
                    add("extra_column", tc.name, col.name,
                        expected="not in contract", actual=col.col_type)
    return report


def check_sql_text(sql_text: str, dialect: str = "hive",
                   contract: str = "", root: str = "<inline>",
                   ) -> ContractReport:
    return _check_text(sql_text, contract, dialect, root)


def check_files(paths: list[Path] | list[str], dialect: str = "hive",
                contract: str = "", root: str = "") -> ContractReport:
    resolved = [Path(p) for p in paths]
    text = "\n;\n".join(p.read_text(encoding="utf-8") for p in resolved)
    return _check_text(text, contract, dialect, root or str(resolved[0]))


def check_dir(directory: str | Path, dialect: str = "hive",
              contract: str = "") -> ContractReport:
    base = Path(directory)
    files = sorted(base.rglob("*.sql"))
    text = "\n;\n".join(p.read_text(encoding="utf-8") for p in files)
    return _check_text(text, contract, dialect, str(base))
