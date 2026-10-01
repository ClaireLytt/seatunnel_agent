# -*- coding: utf-8 -*-
"""Deterministic schema parsing and drift detection.

Type-change classification: a *widening* change within the same family
(INT→BIGINT, FLOAT→DOUBLE, VARCHAR(50)→VARCHAR(100)/STRING, DECIMAL with
larger precision and same scale) is a **risk**; any other change is
**breaking**. A removed+added column pair with identical type and comment
is collapsed into one "possible rename" risk finding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..data_lineage.graph import norm_table

SEVERITIES = ("breaking", "risk", "info")
_SEV_RANK = {"info": 1, "risk": 2, "breaking": 3}


@dataclass
class ColumnSchema:
    name: str
    col_type: str
    comment: str = ""
    is_partition: bool = False


@dataclass
class TableSchema:
    name: str
    columns: dict[str, ColumnSchema] = field(default_factory=dict)
    partition_cols: list[str] = field(default_factory=list)
    comment: str = ""


@dataclass
class DriftFinding:
    kind: str          # table_removed | table_added | column_removed |
                       # column_added | type_changed | comment_changed |
                       # partition_changed | column_renamed
    severity: str      # breaking | risk | info
    table: str
    column: str = ""
    old: str = ""
    new: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity,
                "table": self.table, "column": self.column,
                "old": self.old, "new": self.new}


@dataclass
class DriftReport:
    old_root: str
    new_root: str
    dialect: str
    findings: list[DriftFinding] = field(default_factory=list)
    tables_old: int = 0
    tables_new: int = 0
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {level: 0 for level in SEVERITIES}
        for f in self.findings:
            out[f.severity] += 1
        out["total"] = len(self.findings)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_root": self.old_root,
            "new_root": self.new_root,
            "dialect": self.dialect,
            "tables_old": self.tables_old,
            "tables_new": self.tables_new,
            "counts": self.counts(),
            "findings": [f.to_dict() for f in self.findings],
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# DDL parsing
# ---------------------------------------------------------------------------

def parse_schema_script(sql_text: str, dialect: str = "hive",
                        ) -> tuple[dict[str, TableSchema], list[str]]:
    """Every CREATE TABLE in *sql_text* → {table: TableSchema}."""
    import sqlglot
    from sqlglot import exp

    from ..data_lineage.sqlglot_lineage import resolve_sqlglot_dialect

    read = resolve_sqlglot_dialect(dialect)
    tables: dict[str, TableSchema] = {}
    warnings: list[str] = []
    try:
        statements = sqlglot.parse(sql_text, read=read)
    except sqlglot.errors.ParseError as exc:
        return {}, [f"DDL 解析失败: {exc}"]
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
        name = norm_table(".".join(parts))
        schema = TableSchema(name=name)
        prop = tree.find(exp.SchemaCommentProperty)
        if prop is not None and prop.this is not None:
            schema.comment = prop.this.name
        part_prop = tree.find(exp.PartitionedByProperty)
        part_cols: list[str] = []
        if part_prop is not None:
            part_cols = [cd.name.lower() for cd in
                         part_prop.find_all(exp.ColumnDef)]
        schema.partition_cols = part_cols
        for cd in tree.find_all(exp.ColumnDef):
            if not cd.name:
                continue
            kind = cd.args.get("kind")
            try:
                col_type = (kind.sql(dialect=read).upper()
                            if kind is not None else "")
            except Exception:  # noqa: BLE001 — type rendering is best-effort
                col_type = str(kind or "").upper()
            comment = ""
            for c in cd.args.get("constraints") or []:
                if isinstance(c.kind, exp.CommentColumnConstraint):
                    comment = c.kind.this.name
            col = cd.name.lower()
            schema.columns[col] = ColumnSchema(
                name=col, col_type=col_type, comment=comment,
                is_partition=col in part_cols)
        tables[name] = schema
    return tables, warnings


def load_schemas(path: str | Path, dialect: str = "hive",
                 ) -> tuple[dict[str, TableSchema], list[str]]:
    """File or directory (recursive *.sql) → merged {table: TableSchema}."""
    from ..sql_review.runner import collect_sql_files

    p = Path(path)
    files = collect_sql_files(p) if p.is_dir() else [p]
    tables: dict[str, TableSchema] = {}
    warnings: list[str] = []
    if p.is_dir() and not files:
        return {}, [f"目录 {path} 下没有找到 *.sql 文件"]
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            warnings.append(f"无法读取 {f}: {exc}")
            continue
        parsed, warn = parse_schema_script(text, dialect)
        warnings.extend(f"{f}: {w}" for w in warn)
        for name, schema in parsed.items():
            if name in tables:
                warnings.append(f"{f}: 表 {name} 重复定义，后者覆盖前者")
            tables[name] = schema
    return tables, warnings


# ---------------------------------------------------------------------------
# type-change classification
# ---------------------------------------------------------------------------

_INT_RANK = {"TINYINT": 1, "SMALLINT": 2, "INT": 3, "INTEGER": 3, "BIGINT": 4}
_FLOAT_RANK = {"FLOAT": 1, "REAL": 1, "DOUBLE": 2}
_DECIMAL_RE = re.compile(r"^(?:DECIMAL|NUMERIC)\((\d+)\s*,\s*(\d+)\)$")
_VARCHAR_RE = re.compile(r"^(?:VAR)?CHAR\((\d+)\)$")
_TEXTY = {"STRING", "TEXT"}


def classify_type_change(old: str, new: str) -> str:
    """'risk' for widening changes, 'breaking' for everything else."""
    old, new = old.strip().upper(), new.strip().upper()
    if old == new:
        return ""
    if old in _INT_RANK and new in _INT_RANK:
        return "risk" if _INT_RANK[new] > _INT_RANK[old] else "breaking"
    if old in _FLOAT_RANK and new in _FLOAT_RANK:
        return "risk" if _FLOAT_RANK[new] > _FLOAT_RANK[old] else "breaking"
    om, nm = _DECIMAL_RE.match(old), _DECIMAL_RE.match(new)
    if om and nm:
        op, os_ = int(om.group(1)), int(om.group(2))
        np, ns = int(nm.group(1)), int(nm.group(2))
        return ("risk" if np >= op and ns == os_ else "breaking")
    ov, nv = _VARCHAR_RE.match(old), _VARCHAR_RE.match(new)
    if ov and (nv or new in _TEXTY):
        if new in _TEXTY or int(nv.group(1)) >= int(ov.group(1)):
            return "risk"
        return "breaking"
    return "breaking"


# ---------------------------------------------------------------------------
# diffing
# ---------------------------------------------------------------------------

def _diff_table(old: TableSchema, new: TableSchema) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    t = old.name
    # partition columns appearing/disappearing are already covered by the
    # partition_changed finding — don't double-report them as add/remove
    removed = [c for c in old.columns if c not in new.columns
               and not old.columns[c].is_partition]
    added = [c for c in new.columns if c not in old.columns
             and not new.columns[c].is_partition]

    # collapse an obvious rename: one removed + one added with the same type,
    # backed by a matching non-empty comment OR similar names — two empty
    # comments are no evidence, and must not hide a breaking column removal
    if len(removed) == 1 and len(added) == 1:
        import difflib

        oc, nc = old.columns[removed[0]], new.columns[added[0]]
        comment_match = bool(oc.comment) and oc.comment == nc.comment
        name_similar = difflib.SequenceMatcher(
            None, oc.name, nc.name).ratio() >= 0.6
        if oc.col_type == nc.col_type and (comment_match or name_similar):
            findings.append(DriftFinding(
                kind="column_renamed", severity="risk", table=t,
                column=oc.name, old=oc.name, new=nc.name))
            removed, added = [], []

    for c in removed:
        findings.append(DriftFinding(
            kind="column_removed", severity="breaking", table=t, column=c,
            old=old.columns[c].col_type))
    for c in added:
        findings.append(DriftFinding(
            kind="column_added", severity="info", table=t, column=c,
            new=new.columns[c].col_type))
    for c, oc in old.columns.items():
        nc = new.columns.get(c)
        if nc is None:
            continue
        sev = classify_type_change(oc.col_type, nc.col_type)
        if sev:
            findings.append(DriftFinding(
                kind="type_changed", severity=sev, table=t, column=c,
                old=oc.col_type, new=nc.col_type))
        if oc.comment != nc.comment:
            findings.append(DriftFinding(
                kind="comment_changed", severity="info", table=t, column=c,
                old=oc.comment, new=nc.comment))
    if old.partition_cols != new.partition_cols:
        findings.append(DriftFinding(
            kind="partition_changed", severity="breaking", table=t,
            old=", ".join(old.partition_cols) or "-",
            new=", ".join(new.partition_cols) or "-"))
    return findings


def diff_schemas(old: dict[str, TableSchema], new: dict[str, TableSchema],
                 ) -> list[DriftFinding]:
    findings: list[DriftFinding] = []
    for name in old:
        if name not in new:
            findings.append(DriftFinding(
                kind="table_removed", severity="breaking", table=name))
    for name in new:
        if name not in old:
            findings.append(DriftFinding(
                kind="table_added", severity="info", table=name))
    for name, old_schema in old.items():
        if name in new:
            findings.extend(_diff_table(old_schema, new[name]))
    findings.sort(key=lambda f: (-_SEV_RANK[f.severity], f.table, f.column))
    return findings


def diff_scripts(old_sql: str, new_sql: str, dialect: str = "hive",
                 old_root: str = "<old>", new_root: str = "<new>",
                 ) -> DriftReport:
    old_tables, w1 = parse_schema_script(old_sql, dialect)
    new_tables, w2 = parse_schema_script(new_sql, dialect)
    report = DriftReport(old_root=old_root, new_root=new_root,
                         dialect=dialect,
                         warnings=[f"old: {w}" for w in w1]
                         + [f"new: {w}" for w in w2])
    report.tables_old, report.tables_new = len(old_tables), len(new_tables)
    report.findings = diff_schemas(old_tables, new_tables)
    return report


def diff_paths(old_path: str | Path, new_path: str | Path,
               dialect: str = "hive") -> DriftReport:
    old_tables, w1 = load_schemas(old_path, dialect)
    new_tables, w2 = load_schemas(new_path, dialect)
    report = DriftReport(old_root=str(old_path), new_root=str(new_path),
                         dialect=dialect,
                         warnings=[f"old: {w}" for w in w1]
                         + [f"new: {w}" for w in w2])
    report.tables_old, report.tables_new = len(old_tables), len(new_tables)
    report.findings = diff_schemas(old_tables, new_tables)
    return report
