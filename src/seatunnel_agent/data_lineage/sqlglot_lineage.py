# -*- coding: utf-8 -*-
"""Optional sqlglot-powered column lineage (install extras: ``lineage``).

With sqlglot installed, column edges come from a real AST — alias resolution,
JOIN qualification and aggregation detection are more reliable than the regex
tracer. Without it (or on any parse failure) ``extract_column_edges`` returns
``None`` and callers fall back to the regex path unchanged.
"""

from __future__ import annotations

from .graph import ColumnEdge

try:
    import sqlglot
    from sqlglot import exp
except ImportError:  # pragma: no cover — exercised via monkeypatch in tests
    sqlglot = None
    exp = None


def sqlglot_available() -> bool:
    return sqlglot is not None


def _top_selects(tree) -> list:
    """Top-level SELECTs feeding the target (INSERT/CTAS body, UNION branches)."""
    node = tree
    if isinstance(node, (exp.Insert, exp.Create)):
        node = node.expression
    set_op = getattr(exp, "SetOperation", exp.Union)
    selects: list = []

    def walk(n) -> None:
        if isinstance(n, exp.Select):
            selects.append(n)
        elif isinstance(n, set_op):
            walk(n.this)
            walk(n.expression)
        elif isinstance(n, (exp.Subquery, exp.Paren)):
            walk(n.this)

    walk(node)
    return selects


def _table_mapping(select) -> dict[str, str]:
    """alias-or-name → full table name, from this SELECT's FROM/JOINs only."""
    tables = []
    # sqlglot renamed the arg key "from" → "from_" across versions.
    from_ = select.args.get("from") or select.args.get("from_")
    if from_ is not None:
        tables.append(from_.this)
    for join in select.args.get("joins") or []:
        tables.append(join.this)
    mapping: dict[str, str] = {}
    for t in tables:
        if isinstance(t, exp.Table):
            full = f"{t.db}.{t.name}" if t.db else t.name
            mapping[t.alias_or_name.lower()] = full.lower()
    return mapping


def extract_column_edges(
    statement: str,
    target: str,
    sources: list[str],
) -> list[ColumnEdge] | None:
    """Column edges from the AST, or None to signal regex fallback."""
    if sqlglot is None:
        return None
    try:
        tree = sqlglot.parse_one(statement, read="hive")
    except Exception:  # noqa: BLE001 — any parse failure means fallback
        return None

    selects = _top_selects(tree)
    if not selects:
        return None

    fallback_sole = sources[0] if len(sources) == 1 else ""
    edges: list[ColumnEdge] = []
    seen: set[tuple[str, str, str]] = set()
    for select in selects:
        mapping = _table_mapping(select)
        sole = next(iter(mapping.values())) if len(mapping) == 1 else fallback_sole
        for proj in select.expressions:
            out_name = proj.alias_or_name
            if not out_name or out_name == "*":
                continue
            is_agg = proj.find(exp.AggFunc) is not None
            expression = proj.sql(dialect="hive")
            for col in proj.find_all(exp.Column):
                if col.table:
                    src_table = mapping.get(col.table.lower(), "")
                else:
                    src_table = sole
                if not src_table or not col.name:
                    continue
                key = (src_table, col.name.lower(), out_name.lower())
                if key in seen:
                    continue
                seen.add(key)
                edges.append(ColumnEdge(
                    src_table=src_table,
                    src_column=col.name,
                    dst_table=target,
                    dst_column=out_name,
                    expression=expression,
                    is_aggregation=is_agg,
                ))
    return edges
