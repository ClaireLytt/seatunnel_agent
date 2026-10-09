# -*- coding: utf-8 -*-
"""Normalized table model for the sync generator.

Two schema shapes exist in this project (``text2sql.schema.TableSchema``
from live introspection, ``schema_drift.differ.TableSchema`` from offline
DDL). Both converge into :class:`TableSpec` here; everything downstream
(type mapping, DDL rendering, config generation) sees one shape only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ColumnSpec:
    name: str
    mysql_type: str          # raw MySQL type, e.g. "decimal(12, 2)" / "bigint unsigned"
    comment: str = ""
    nullable: bool = True    # best-effort; True when unknown


@dataclass
class TableSpec:
    database: str
    name: str
    comment: str = ""
    columns: list[ColumnSpec] = field(default_factory=list)
    primary_keys: list[str] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.database}.{self.name}" if self.database else self.name


# ---------------------------------------------------------------------------
# adapters
# ---------------------------------------------------------------------------

def from_live(ts) -> TableSpec:
    """``text2sql.schema.TableSchema`` (live DB introspection) → TableSpec.

    Primary keys stay empty — the executor's INFORMATION_SCHEMA query
    doesn't fetch key info (deferred; DDL renderers fall back to
    DUPLICATE KEY with a warning).
    """
    cols = [ColumnSpec(name=c.name, mysql_type=c.dtype, comment=c.comment)
            for c in list(ts.columns) + list(ts.partition_columns)]
    return TableSpec(database=ts.database or "", name=ts.name,
                     comment=ts.comment, columns=cols)


def load_from_ddl(path: str | Path,
                  ) -> tuple[list[TableSpec], list[str]]:
    """Offline path: DDL file or directory → normalized TableSpecs.

    Columns/comments come from ``schema_drift.differ`` (sqlglot, mysql
    dialect preserves UNSIGNED / ENUM(...) / TINYINT(1)); a sibling
    sqlglot pass recovers what the differ drops: PRIMARY KEY constraints
    and NOT NULL flags.
    """
    from ..schema_drift.differ import load_schemas
    from ..sql_review.runner import collect_sql_files

    tables, warnings = load_schemas(path, dialect="mysql")

    p = Path(path)
    files = collect_sql_files(p) if p.is_dir() else [p]
    pks: dict[str, list[str]] = {}
    not_null: dict[str, set[str]] = {}
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # already warned by load_schemas
        file_pks, file_nn = _extract_constraints(text)
        pks.update(file_pks)
        not_null.update(file_nn)

    specs: list[TableSpec] = []
    for name, schema in tables.items():
        db, _, bare = name.rpartition(".")
        nn = not_null.get(name, set())
        cols = [ColumnSpec(name=c.name, mysql_type=c.col_type,
                           comment=c.comment, nullable=c.name not in nn)
                for c in schema.columns.values()]
        specs.append(TableSpec(
            database=db, name=bare, comment=schema.comment,
            columns=cols, primary_keys=pks.get(name, [])))
    return specs, warnings


def _extract_constraints(sql_text: str,
                         ) -> tuple[dict[str, list[str]], dict[str, set[str]]]:
    """{table: [pk cols]} and {table: {not-null cols}} per CREATE TABLE."""
    import sqlglot
    from sqlglot import exp

    from ..data_lineage.graph import norm_table

    pks: dict[str, list[str]] = {}
    not_null: dict[str, set[str]] = {}
    try:
        statements = sqlglot.parse(sql_text, read="mysql")
    except sqlglot.errors.ParseError:
        return pks, not_null
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
        keys: list[str] = []
        nn: set[str] = set()
        for pk in tree.find_all(exp.PrimaryKey):
            keys.extend(c.name.lower() for c in pk.expressions)
        for cd in tree.find_all(exp.ColumnDef):
            for c in cd.args.get("constraints") or []:
                if isinstance(c.kind, exp.PrimaryKeyColumnConstraint):
                    keys.append(cd.name.lower())
                elif isinstance(c.kind, exp.NotNullColumnConstraint):
                    nn.add(cd.name.lower())
        if keys:
            # 去重保序（PRIMARY KEY (id, id) 之类的脏 DDL）
            pks[name] = list(dict.fromkeys(keys))
        if nn:
            not_null[name] = nn
    return pks, not_null
