# -*- coding: utf-8 -*-
"""Execute the generated data + query on in-memory SQLite (stdlib).

Hive/Spark SQL is transpiled to the sqlite dialect via sqlglot; qualified
table names (``db.table``) are flattened because SQLite has no schemas.
Functions SQLite lacks make the validation *inconclusive* (transpile or
exec error with the reason) — never a crash, and never a claim that the
query is wrong.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from .generator import GenResult


@dataclass
class ValidationResult:
    status: str          # ok | transpile_error | exec_error | skipped
    detail: str = ""
    row_count: int = -1
    sqlite_sql: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "detail": self.detail,
                "row_count": self.row_count}


def _flat(name: str) -> str:
    return name.replace(".", "__")


def _sqlite_type(col_type: str) -> str:
    t = (col_type or "").upper()
    if t in ("TINYINT", "SMALLINT", "INT", "INTEGER", "BIGINT"):
        return "INTEGER"
    if t in ("FLOAT", "DOUBLE", "REAL") or t.startswith(("DECIMAL",
                                                         "NUMERIC")):
        return "REAL"
    return "TEXT"


def _to_sqlite_query(sql: str, dialect: str) -> str:
    import sqlglot
    from sqlglot import exp

    from ..data_lineage.sqlglot_lineage import resolve_sqlglot_dialect

    read = resolve_sqlglot_dialect(dialect)
    tree = sqlglot.parse_one(sql, read=read)
    if isinstance(tree, exp.Insert) and tree.expression is not None:
        # validate the SELECT part only; Hive WITH ... INSERT keeps the CTEs
        # on the Insert node, so carry them over or they read as tables
        select = tree.expression
        for with_key in ("with_", "with"):
            if tree.args.get(with_key) is not None:
                select.set(with_key, tree.args[with_key])
                break
        tree = select
    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        if t.name.lower() in cte_names and not t.db:
            continue
        parts = [p for p in (t.catalog, t.db, t.name) if p]
        t.set("catalog", None)
        t.set("db", None)
        t.set("this", exp.to_identifier(_flat(".".join(parts).lower())))
    return tree.sql(dialect="sqlite")


def validate_with_sqlite(result: GenResult) -> ValidationResult:
    if not result.tables:
        return ValidationResult(status="skipped", detail="no tables")
    try:
        query = _to_sqlite_query(result.query, result.dialect)
    except Exception as exc:  # noqa: BLE001 — unsupported syntax is a finding
        return ValidationResult(status="transpile_error",
                                detail=f"{type(exc).__name__}: {exc}")
    conn = sqlite3.connect(":memory:")
    try:
        cur = conn.cursor()
        for table in result.tables:
            cols = ", ".join(
                f"{c.name} {_sqlite_type(c.col_type)}" for c in table.columns)
            cur.execute(f"CREATE TABLE {_flat(table.name)} ({cols})")
            marks = ", ".join("?" for _ in table.columns)
            cur.executemany(
                f"INSERT INTO {_flat(table.name)} VALUES ({marks})",
                table.rows)
        rows = cur.execute(query).fetchall()
        return ValidationResult(status="ok", row_count=len(rows),
                                sqlite_sql=query)
    except sqlite3.Error as exc:
        return ValidationResult(status="exec_error", detail=str(exc),
                                sqlite_sql=query)
    finally:
        conn.close()
