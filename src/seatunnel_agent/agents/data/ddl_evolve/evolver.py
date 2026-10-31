"""Deterministic DDL migration-script generation from a schema diff.

schema_drift *reports* how two DDL snapshots differ; this agent turns
that diff into an executable migration script.  Safe changes become
real statements — ADD COLUMNS, CHANGE COLUMN for widenings, renames and
comment updates, full CREATE TABLE for new tables — while dangerous
changes (dropped columns or tables, narrowing or incompatible type
changes, partition-layout changes) are emitted as **commented-out**
statements with a warning line, so nothing destructive can run by
accident.  Hive and MySQL spellings supported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["EvolvePlan", "EvolveStep", "build_migration"]

_DIALECTS = ("hive", "mysql")


@dataclass
class EvolveStep:
    kind: str            # the drift kind behind the statement
    table: str
    sql: str             # executable, or commented-out when unsafe
    safe: bool = True    # False = emitted commented with a warning
    note: str = ""       # why it is unsafe / what to decide first

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "table": self.table, "sql": self.sql,
                "safe": self.safe, "note": self.note}


@dataclass
class EvolvePlan:
    dialect: str
    steps: list[EvolveStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def safe_steps(self) -> int:
        return sum(1 for s in self.steps if s.safe)

    @property
    def unsafe_steps(self) -> int:
        return sum(1 for s in self.steps if not s.safe)

    def to_script(self) -> str:
        """The paste-ready migration script."""
        out: list[str] = []
        for s in self.steps:
            if s.note:
                out.append(f"-- [REVIEW] {s.note}")
            out.append(s.sql)
            out.append("")
        return "\n".join(out).rstrip() + "\n" if out else ""

    def to_dict(self) -> dict[str, Any]:
        return {"dialect": self.dialect,
                "steps_total": len(self.steps),
                "safe_steps": self.safe_steps,
                "unsafe_steps": self.unsafe_steps,
                "steps": [s.to_dict() for s in self.steps],
                "script": self.to_script(),
                "warnings": list(self.warnings)}


def _comment_sql(comment: str) -> str:
    return " COMMENT '" + comment.replace("'", "''") + "'" if comment else ""


def _render_create(schema, dialect: str) -> str:
    cols = [c for c in schema.columns.values() if not c.is_partition]
    body = ",\n".join(f"  {c.name} {c.col_type}{_comment_sql(c.comment)}"
                      for c in cols)
    sql = f"CREATE TABLE {schema.name} (\n{body}\n)"
    if schema.comment:
        sql += f"\nCOMMENT '{schema.comment}'"
    if schema.partition_cols and dialect == "hive":
        parts = ", ".join(
            f"{schema.columns[p].name} {schema.columns[p].col_type}"
            if p in schema.columns else f"{p} STRING"
            for p in schema.partition_cols)
        sql += f"\nPARTITIONED BY ({parts})"
    return sql + ";"


def _change_column(table: str, column: str, col_type: str, comment: str,
                   dialect: str, new_name: str = "") -> str:
    name_to = new_name or column
    if dialect == "mysql":
        return (f"ALTER TABLE {table} CHANGE COLUMN {column} {name_to} "
                f"{col_type}{_comment_sql(comment)};")
    return (f"ALTER TABLE {table} CHANGE COLUMN {column} {name_to} "
            f"{col_type}{_comment_sql(comment)};")


def _commented(sql: str) -> str:
    return "\n".join("-- " + line for line in sql.splitlines())


def build_migration(old_sql: str, new_sql: str,
                    dialect: str = "hive") -> EvolvePlan:
    """Old DDL x new DDL → migration plan (schema_drift diff reused)."""
    from seatunnel_agent.agents.data.schema_drift.differ import (
        diff_scripts,
        parse_schema_script,
    )

    if dialect not in _DIALECTS:
        raise ValueError(f"dialect must be one of {_DIALECTS}")
    report = diff_scripts(old_sql, new_sql, dialect=dialect)
    if not report.tables_old and not report.tables_new:
        raise ValueError("no CREATE TABLE found on either side")
    new_tables, _ = parse_schema_script(new_sql, dialect)
    old_tables, _ = parse_schema_script(old_sql, dialect)

    plan = EvolvePlan(dialect=dialect, warnings=list(report.warnings))

    def add(kind: str, table: str, sql: str, safe: bool = True,
            note: str = "") -> None:
        plan.steps.append(EvolveStep(kind=kind, table=table,
                                     sql=sql if safe else _commented(sql),
                                     safe=safe, note=note))

    for f in report.findings:
        if f.kind == "table_added":
            schema = next(s for n, s in new_tables.items()
                          if n == f.table)
            add(f.kind, f.table, _render_create(schema, dialect))
        elif f.kind == "table_removed":
            add(f.kind, f.table, f"DROP TABLE {f.table};", safe=False,
                note="dropping a table is irreversible — archive first")
        elif f.kind == "column_added":
            nc = new_tables[f.table].columns[f.column]
            if dialect == "mysql":
                sql = (f"ALTER TABLE {f.table} ADD COLUMN {nc.name} "
                       f"{nc.col_type}{_comment_sql(nc.comment)};")
            else:
                sql = (f"ALTER TABLE {f.table} ADD COLUMNS ({nc.name} "
                       f"{nc.col_type}{_comment_sql(nc.comment)});")
            add(f.kind, f.table, sql)
        elif f.kind == "column_removed":
            if dialect == "mysql":
                sql = f"ALTER TABLE {f.table} DROP COLUMN {f.column};"
            else:
                sql = (f"ALTER TABLE {f.table} REPLACE COLUMNS (...);  "
                       f"-- rebuild without {f.column}")
            add(f.kind, f.table, sql, safe=False,
                note=f"dropping column {f.column} loses data — confirm "
                     "no consumer reads it")
        elif f.kind == "type_changed":
            oc = old_tables[f.table].columns[f.column]
            sql = _change_column(f.table, f.column, f.new,
                                 oc.comment, dialect)
            if f.severity == "risk":      # widening — safe to run
                add(f.kind, f.table, sql)
            else:
                add(f.kind, f.table, sql, safe=False,
                    note=f"narrowing/incompatible {f.old} -> {f.new} "
                         "can truncate or fail — backfill a new column "
                         "instead")
        elif f.kind == "column_renamed":
            oc = old_tables[f.table].columns[f.old]
            add(f.kind, f.table,
                _change_column(f.table, f.old, oc.col_type, oc.comment,
                               dialect, new_name=f.new))
        elif f.kind == "comment_changed":
            nc = new_tables[f.table].columns[f.column]
            add(f.kind, f.table,
                _change_column(f.table, f.column, nc.col_type,
                               nc.comment, dialect))
        elif f.kind == "partition_changed":
            add(f.kind, f.table,
                f"-- partition layout {f.old} -> {f.new}", safe=False,
                note="partition layout cannot be altered in place — "
                     "create the new table, backfill, swap")
    return plan
