"""Migration DDL generation from a drift report (漂移 → ALTER 语句).

Closes the loop after ``schemadiff``: additive / in-place changes become
ready-to-run ALTER statements, while destructive ones (drop column / drop
table / repartition) are NEVER auto-applied — they are emitted as commented
``MANUAL REVIEW`` blocks so a human stays in the loop.

Deterministic string assembly only; identical inputs produce identical
scripts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .differ import DriftReport, TableSchema

#: dialects that use MySQL-style ALTER syntax
_MYSQL_LIKE = {"mysql", "doris", "starrocks", "tidb", "oceanbase"}

_TYPE_PLACEHOLDER = "<TYPE>"


@dataclass
class MigrationStatement:
    table: str
    kind: str          # mirrors DriftFinding.kind
    sql: str
    auto: bool         # False -> destructive/incomplete, needs human review
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "kind": self.kind, "sql": self.sql,
                "auto": self.auto, "note": self.note}


@dataclass
class MigrationPlan:
    dialect: str
    statements: list[MigrationStatement] = field(default_factory=list)

    @property
    def auto_count(self) -> int:
        return sum(1 for s in self.statements if s.auto)

    @property
    def manual_count(self) -> int:
        return sum(1 for s in self.statements if not s.auto)

    def to_dict(self) -> dict[str, Any]:
        return {"dialect": self.dialect, "auto": self.auto_count,
                "manual": self.manual_count,
                "statements": [s.to_dict() for s in self.statements]}


def _col_type(
    new_schemas: dict[str, TableSchema] | None, table: str, column: str,
) -> str:
    if new_schemas and table in new_schemas:
        col = new_schemas[table].columns.get(column)
        if col is not None:
            return col.col_type
    return _TYPE_PLACEHOLDER


def generate_migration(
    report: DriftReport,
    new_schemas: dict[str, TableSchema] | None = None,
) -> MigrationPlan:
    """Turn drift findings into an ordered migration plan.

    ``new_schemas`` (the parsed NEW snapshot, e.g. from ``load_schemas``)
    supplies column types for statements the findings alone cannot complete
    (rename / comment change); without it those carry a ``<TYPE>``
    placeholder and are downgraded to manual.
    """
    dialect = (report.dialect or "hive").lower()
    mysqlish = dialect in _MYSQL_LIKE
    plan = MigrationPlan(dialect=dialect)

    for f in report.findings:
        t, c = f.table, f.column
        if f.kind == "column_added":
            sql = (
                f"ALTER TABLE {t} ADD COLUMN {c} {f.new};" if mysqlish
                else f"ALTER TABLE {t} ADD COLUMNS ({c} {f.new});"
            )
            plan.statements.append(MigrationStatement(t, f.kind, sql, auto=True))
        elif f.kind == "type_changed":
            sql = (
                f"ALTER TABLE {t} MODIFY COLUMN {c} {f.new};" if mysqlish
                else f"ALTER TABLE {t} CHANGE COLUMN {c} {c} {f.new};"
            )
            # a widening change is safe; a breaking one still needs eyes
            auto = f.severity != "breaking"
            note = "" if auto else f"类型收窄/不兼容 ({f.old} -> {f.new})，确认下游后再执行"
            plan.statements.append(
                MigrationStatement(t, f.kind, sql, auto=auto, note=note))
        elif f.kind == "column_renamed":
            typ = _col_type(new_schemas, t, f.new)
            sql = (
                f"ALTER TABLE {t} RENAME COLUMN {f.old} TO {f.new};" if mysqlish
                else f"ALTER TABLE {t} CHANGE COLUMN {f.old} {f.new} {typ};"
            )
            auto = mysqlish or typ != _TYPE_PLACEHOLDER
            note = "" if auto else "无法从 diff 推出列类型，补全后执行"
            plan.statements.append(
                MigrationStatement(t, f.kind, sql, auto=auto, note=note))
        elif f.kind == "comment_changed":
            typ = _col_type(new_schemas, t, c)
            comment = f.new.replace("'", "''")
            sql = (
                f"ALTER TABLE {t} MODIFY COLUMN {c} {typ} COMMENT '{comment}';"
                if mysqlish else
                f"ALTER TABLE {t} CHANGE COLUMN {c} {c} {typ} COMMENT '{comment}';"
            )
            auto = typ != _TYPE_PLACEHOLDER
            note = "" if auto else "无法从 diff 推出列类型，补全后执行"
            plan.statements.append(
                MigrationStatement(t, f.kind, sql, auto=auto, note=note))
        elif f.kind == "column_removed":
            plan.statements.append(MigrationStatement(
                t, f.kind, f"ALTER TABLE {t} DROP COLUMN {c};", auto=False,
                note="破坏性变更：确认无下游引用后手工执行"))
        elif f.kind == "table_removed":
            plan.statements.append(MigrationStatement(
                t, f.kind, f"DROP TABLE {t};", auto=False,
                note="破坏性变更：确认无下游引用后手工执行"))
        elif f.kind == "table_added":
            plan.statements.append(MigrationStatement(
                t, f.kind, f"-- 新表 {t}: 直接执行新快照中的 CREATE TABLE 语句",
                auto=False, note="CREATE 语句以新 DDL 快照为准"))
        elif f.kind == "partition_changed":
            plan.statements.append(MigrationStatement(
                t, f.kind,
                f"-- 分区变更 {t}: {f.old} -> {f.new}（通常需重建表并回灌数据）",
                auto=False, note="分区结构无法原地 ALTER"))
    return plan


def render_migration_sql(plan: MigrationPlan) -> str:
    """One runnable .sql script: auto statements plain, manual ones
    commented out under a MANUAL REVIEW banner."""
    lines = [
        f"-- migration generated by schemadiff (dialect: {plan.dialect})",
        f"-- auto: {plan.auto_count} / manual review: {plan.manual_count}",
        "",
    ]
    autos = [s for s in plan.statements if s.auto]
    manuals = [s for s in plan.statements if not s.auto]
    for s in autos:
        lines.append(s.sql)
    if manuals:
        lines += ["", "-- ======== MANUAL REVIEW (not auto-applied) ========"]
        for s in manuals:
            if s.note:
                lines.append(f"-- {s.note}")
            prefix = "" if s.sql.startswith("--") else "-- "
            lines.append(f"{prefix}{s.sql}")
    lines.append("")
    return "\n".join(lines)
