# -*- coding: utf-8 -*-
"""Deterministic test-data generation core.

Pipeline: parse the query → physical tables + referenced columns per table
(CTEs excluded) → merge DDL schemas → infer missing types from usage and
naming → union-find equi-join columns into shared value pools → honor
literal predicates → emit rows with boundary cases mixed in.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..data_lineage.graph import norm_table

DEFAULT_ROWS = 5
MAX_ROWS = 100

_ID_RE = re.compile(r"(^|_)id$|^id($|_)")
_CNT_RE = re.compile(r"(^|_)(cnt|count|num|qty|quantity)($|_)")
_AMT_RE = re.compile(r"(^|_)(amount|amt|price|fee|money|gmv|revenue)($|_)")
_DATE_RE = re.compile(r"(^|_)(dt|date|day|ds)($|_)")
_NUMERIC_TYPES = {"TINYINT", "SMALLINT", "INT", "INTEGER", "BIGINT"}
_FLOAT_TYPES = {"FLOAT", "DOUBLE", "REAL"}
_BASE_DATE = date(2024, 1, 1)


@dataclass
class ColumnSpec:
    name: str
    col_type: str = "STRING"       # normalized upper
    source: str = "inferred"       # ddl | inferred
    comment: str = ""
    join_group: int = -1           # shared value pool id, -1 = none
    required_values: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "type": self.col_type,
                "source": self.source,
                "required_values": list(self.required_values)}


@dataclass
class TableData:
    name: str
    columns: list[ColumnSpec] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)

    def csv_text(self) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow([c.name for c in self.columns])
        for row in self.rows:
            writer.writerow(["" if v is None else v for v in row])
        return buf.getvalue()

    def create_sql(self) -> str:
        cols = ",\n".join(f"  {c.name} {c.col_type}" for c in self.columns)
        return f"CREATE TABLE {self.name} (\n{cols}\n);"

    def insert_sql(self) -> str:
        def lit(v: Any) -> str:
            if v is None:
                return "NULL"
            if isinstance(v, (int, float)):
                return str(v)
            return "'" + str(v).replace("'", "''") + "'"

        values = ",\n".join(
            "  (" + ", ".join(lit(v) for v in row) + ")"
            for row in self.rows)
        names = ", ".join(c.name for c in self.columns)
        return f"INSERT INTO {self.name} ({names}) VALUES\n{values};"

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name,
                "columns": [c.to_dict() for c in self.columns],
                "rows": [["" if v is None else v for v in row]
                         for row in self.rows],
                "csv": self.csv_text(),
                "create_sql": self.create_sql(),
                "insert_sql": self.insert_sql()}


@dataclass
class GenResult:
    query: str
    dialect: str
    tables: list[TableData] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    validation: Any = None         # ValidationResult | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dialect": self.dialect,
            "tables": [t.to_dict() for t in self.tables],
            "notes": list(self.notes),
            "warnings": list(self.warnings),
            "validation": (self.validation.to_dict()
                           if self.validation is not None else None),
        }


# ---------------------------------------------------------------------------
# query analysis
# ---------------------------------------------------------------------------

def _table_key(t) -> str:
    parts = [p for p in (t.catalog, t.db, t.name) if p]
    return norm_table(".".join(parts))


def _analyze(tree, dialect: str) -> tuple[
        dict[str, dict[str, ColumnSpec]], list[tuple], list[str]]:
    """(tables→columns, equi-join pairs, notes) from the parsed query."""
    from sqlglot import exp

    notes: list[str] = []
    ctes = list(tree.find_all(exp.CTE))
    cte_names = {c.alias_or_name.lower() for c in ctes}

    def _is_physical(t) -> bool:
        return bool(t.db) or t.name.lower() not in cte_names

    # alias → physical table (per whole statement: good enough for test data)
    alias_map: dict[str, str] = {}
    tables: dict[str, dict[str, ColumnSpec]] = {}
    for t in tree.find_all(exp.Table):
        if not _is_physical(t):
            continue
        key = _table_key(t)
        tables.setdefault(key, {})
        alias = (t.alias or t.name).lower()
        alias_map[alias] = key
        alias_map[t.name.lower()] = key
    # a CTE reading exactly one physical table is transparent for data
    # generation: `base.user_id` attributes (and joins) through to it
    for c in ctes:
        sources = [t for t in c.this.find_all(exp.Table) if _is_physical(t)]
        if len({_table_key(t) for t in sources}) == 1:
            alias_map.setdefault(c.alias_or_name.lower(),
                                 _table_key(sources[0]))

    def resolve(col) -> tuple[str, str] | None:
        """exp.Column → (table, column) or None when it can't be pinned."""
        name = col.name.lower()
        if col.table:
            key = alias_map.get(col.table.lower())
            return (key, name) if key else None
        if len(tables) == 1:
            return (next(iter(tables)), name)
        # unqualified: attribute via the owning SELECT when it reads from
        # exactly one physical table
        sel = col.parent_select
        if sel is not None:
            local = {_table_key(t) for t in sel.find_all(exp.Table)
                     if t.parent_select is sel and _is_physical(t)}
            if len(local) == 1:
                return (next(iter(local)), name)
        return None

    def ensure(key: tuple[str, str]) -> ColumnSpec:
        table, name = key
        spec = tables[table].get(name)
        if spec is None:
            spec = tables[table][name] = ColumnSpec(name=name)
        return spec

    unresolved: set[str] = set()
    for col in tree.find_all(exp.Column):
        target = resolve(col)
        if target is None:
            unresolved.add(col.name.lower())
            continue
        if target[0] in tables:
            ensure(target)

    # equi-joins + literal predicates
    joins: list[tuple[tuple[str, str], tuple[str, str]]] = []
    for eq in tree.find_all(exp.EQ):
        left, right = eq.this, eq.expression
        if isinstance(left, exp.Column) and isinstance(right, exp.Column):
            a, b = resolve(left), resolve(right)
            if a and b and a[0] in tables and b[0] in tables and a != b:
                joins.append((a, b))
            continue
        # literal on either side: WHERE t.a = 5 and WHERE 5 = t.a
        if isinstance(right, exp.Column) and isinstance(left, exp.Literal):
            left, right = right, left
        if isinstance(left, exp.Column) and isinstance(right, exp.Literal):
            target = resolve(left)
            if target and target[0] in tables:
                ensure(target).required_values.append(
                    _literal_value(right))
    for in_expr in tree.find_all(exp.In):
        col = in_expr.this
        if not isinstance(col, exp.Column):
            continue
        target = resolve(col)
        if not target or target[0] not in tables:
            continue
        literals = [e for e in in_expr.expressions
                    if isinstance(e, exp.Literal)]
        if literals:
            ensure(target).required_values.append(
                _literal_value(literals[0]))
    for between in tree.find_all(exp.Between):
        col = between.this
        low = between.args.get("low")
        if isinstance(col, exp.Column) and isinstance(low, exp.Literal):
            target = resolve(col)
            if target and target[0] in tables:
                ensure(target).required_values.append(_literal_value(low))

    if unresolved:
        notes.append("无法归属的列（多表查询中未加表前缀）: "
                     + ", ".join(sorted(unresolved)))
    return tables, joins, notes


def _literal_value(lit) -> Any:
    if lit.is_string:
        return lit.name
    text = lit.name
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


# ---------------------------------------------------------------------------
# type inference
# ---------------------------------------------------------------------------

def _infer_type(spec: ColumnSpec) -> str:
    for v in spec.required_values:
        if isinstance(v, int):
            return "BIGINT"
        if isinstance(v, float):
            return "DOUBLE"
    if _DATE_RE.search(spec.name):
        return "STRING"               # partition-style date string
    if _ID_RE.search(spec.name) or _CNT_RE.search(spec.name):
        return "BIGINT"
    if _AMT_RE.search(spec.name):
        return "DOUBLE"
    return "STRING"


def _apply_ddl(tables: dict[str, dict[str, ColumnSpec]], ddl: str,
               dialect: str, notes: list[str], warnings: list[str]) -> None:
    from ..schema_drift.differ import parse_schema_script

    schemas, warns = parse_schema_script(ddl, dialect)
    warnings.extend(warns)
    for name, schema in schemas.items():
        if name not in tables:
            continue
        referenced = tables[name]
        merged: dict[str, ColumnSpec] = {}
        for col, cs in schema.columns.items():
            spec = referenced.get(col) or ColumnSpec(name=col)
            spec.col_type = cs.col_type or "STRING"
            spec.source = "ddl"
            spec.comment = cs.comment
            merged[col] = spec
        for col, spec in referenced.items():
            if col not in merged:
                merged[col] = spec
                notes.append(f"{name}.{col} 不在 DDL 中，类型按用法推断")
        tables[name] = merged


# ---------------------------------------------------------------------------
# value generation
# ---------------------------------------------------------------------------

def _is_int_type(t: str) -> bool:
    return t.upper() in _NUMERIC_TYPES


def _is_float_type(t: str) -> bool:
    t = t.upper()
    return t in _FLOAT_TYPES or t.startswith(("DECIMAL", "NUMERIC"))


def _date_str(i: int) -> str:
    return (_BASE_DATE + timedelta(days=i)).isoformat()


def _group_value(spec: ColumnSpec, i: int) -> Any:
    """Join-pool values: identical for every column in the group."""
    if _is_int_type(spec.col_type):
        return 1001 + i
    if _is_float_type(spec.col_type):
        return float(1001 + i)
    if _DATE_RE.search(spec.name):
        return _date_str(i % 28)
    return f"k_{i + 1:03d}"


def _plain_value(spec: ColumnSpec, i: int) -> Any:
    if spec.required_values:
        # satisfy the WHERE literal on all but the last plain row, which
        # carries a miss value so filters are provably selective
        return spec.required_values[0]
    if _DATE_RE.search(spec.name):
        return _date_str(i % 28)
    if _is_int_type(spec.col_type):
        return i + 1
    if _is_float_type(spec.col_type):
        return round(10.5 * (i + 1), 2)
    if spec.col_type.upper() in ("DATE",):
        return _date_str(i % 28)
    if spec.col_type.upper().startswith("TIMESTAMP"):
        return f"{_date_str(i % 28)} 00:00:00"
    if spec.col_type.upper() == "BOOLEAN":
        return "true" if i % 2 == 0 else "false"
    return f"{spec.name}_{i + 1}"


def _miss_value(spec: ColumnSpec) -> Any:
    """A value that fails the recorded literal predicate."""
    v = spec.required_values[0]
    if isinstance(v, int):
        return v + 999_999
    if isinstance(v, float):
        return v + 999_999.0
    return f"__miss_{v}"[:60]


def _generate_rows(table: TableData, rows: int) -> None:
    n = max(1, min(rows, MAX_ROWS))
    for i in range(n):
        row: list[Any] = []
        for spec in table.columns:
            if spec.join_group >= 0:
                # literal-constrained pool: the shared literal on all but the
                # miss row (same i-based decision on every table, so the join
                # still matches row-for-row)
                if spec.required_values and not (i == n - 1 and n >= 3):
                    row.append(spec.required_values[0])
                else:
                    row.append(_group_value(spec, i))
            elif spec.required_values and i == n - 1 and n >= 3:
                row.append(_miss_value(spec))
            elif i == n - 2 and n >= 4 and not spec.required_values:
                # boundary row: NULL for every optional column
                row.append(None)
            elif i == n - 3 and n >= 5 and not spec.required_values:
                # boundary row: zero / empty string
                if _is_int_type(spec.col_type):
                    row.append(0)
                elif _is_float_type(spec.col_type):
                    row.append(0.0)
                elif _DATE_RE.search(spec.name):
                    row.append(_date_str(i % 28))
                else:
                    row.append("")
            else:
                row.append(_plain_value(spec, i))
        table.rows.append(row)


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def generate(sql: str, ddl: str = "", rows: int = DEFAULT_ROWS,
             dialect: str = "hive") -> GenResult:
    import sqlglot
    from sqlglot import exp

    from ..data_lineage.sqlglot_lineage import resolve_sqlglot_dialect

    read = resolve_sqlglot_dialect(dialect)
    result = GenResult(query=sql, dialect=dialect)
    try:
        tree = sqlglot.parse_one(sql, read=read)
    except sqlglot.errors.ParseError as exc:
        result.warnings.append(f"查询解析失败: {exc}")
        return result
    # INSERT ... SELECT: generate data for the SELECT's sources only.
    # Hive's WITH ... INSERT hangs the CTEs on the Insert node — transplant
    # them onto the select, or every CTE reads as a physical table.
    if isinstance(tree, exp.Insert) and tree.expression is not None:
        target = tree.this.find(exp.Table) if tree.this is not None else None
        select = tree.expression
        for with_key in ("with_", "with"):
            if tree.args.get(with_key) is not None:
                select.set(with_key, tree.args[with_key])
                break
        tree = select
        result.notes.append(
            "INSERT 语句：目标表 "
            + (_table_key(target) if target is not None else "?")
            + " 不生成数据，仅为来源表生成")

    tables, joins, notes = _analyze(tree, dialect)
    result.notes.extend(notes)
    if not tables:
        result.warnings.append("查询中没有找到物理表")
        return result

    if (ddl or "").strip():
        _apply_ddl(tables, ddl, dialect, result.notes, result.warnings)

    # union-find the equi-join groups into shared value pools
    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in joins:
        parent[find(a)] = find(b)
    group_ids: dict[tuple[str, str], int] = {}
    group_specs: dict[int, list[ColumnSpec]] = {}
    for a, b in joins:
        for key in (a, b):
            root = find(key)
            if root not in group_ids:
                group_ids[root] = len(group_ids)
            table, col = key
            spec = tables[table].get(col)
            if spec is not None:
                spec.join_group = group_ids[root]
                group_specs.setdefault(spec.join_group, []).append(spec)

    # a WHERE literal on any member constrains the whole pool: propagate it
    # so `JOIN ON a.id = b.id WHERE a.id = 5` puts 5 on BOTH sides and the
    # query actually returns rows
    for members in group_specs.values():
        required = next((list(s.required_values) for s in members
                         if s.required_values), None)
        if required:
            for s in members:
                s.required_values = required

    # infer remaining types (after required-value propagation, so both join
    # sides infer the same type from a shared literal)
    for columns in tables.values():
        for spec in columns.values():
            if spec.source != "ddl":
                spec.col_type = _infer_type(spec)

    for name in sorted(tables):
        columns = tables[name]
        if not columns:
            result.notes.append(f"{name}: 查询未引用任何列，跳过")
            continue
        table = TableData(name=name, columns=sorted(
            columns.values(), key=lambda c: (c.source != "ddl", c.name)))
        # DDL tables keep their DDL column order
        if any(c.source == "ddl" for c in table.columns):
            ddl_order = [c for c in columns.values() if c.source == "ddl"]
            extra = [c for c in columns.values() if c.source != "ddl"]
            table.columns = ddl_order + sorted(extra, key=lambda c: c.name)
        _generate_rows(table, rows)
        result.tables.append(table)

    inferred = [f"{t.name}.{c.name}→{c.col_type}"
                for t in result.tables for c in t.columns
                if c.source != "ddl"]
    if inferred:
        result.notes.append("推断类型: " + ", ".join(inferred))
    return result


def write_outputs(result: GenResult, out_dir: str | Path) -> list[Path]:
    """Write {table}.csv + create_tables.sql + inserts.sql under *out_dir*."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for table in result.tables:
        path = out / (table.name.replace(".", "__") + ".csv")
        path.write_text(table.csv_text(), encoding="utf-8-sig")
        written.append(path)
    creates = out / "create_tables.sql"
    creates.write_text(
        "\n\n".join(t.create_sql() for t in result.tables), encoding="utf-8")
    written.append(creates)
    inserts = out / "inserts.sql"
    inserts.write_text(
        "\n\n".join(t.insert_sql() for t in result.tables), encoding="utf-8")
    written.append(inserts)
    return written
