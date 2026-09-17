"""Best-effort SQL data lineage extraction (regex-based).

Parses a SQL query to identify: source tables, output column→source mappings,
join conditions, WHERE filters, GROUP BY columns, and aggregation functions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .schema import SchemaStore
from .validator import (
    _SQL_KEYWORDS,
    _extract_cte_names,
    _strip_literals_and_comments,
    extract_tables,
)


@dataclass
class ColumnLineage:
    output_name: str
    source_table: str = ""
    source_column: str = ""
    expression: str = ""
    is_aggregation: bool = False


@dataclass
class SqlLineage:
    source_tables: list[str] = field(default_factory=list)
    output_columns: list[ColumnLineage] = field(default_factory=list)
    joins: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    cte_names: set[str] = field(default_factory=set)


_AGG_FUNCS = frozenset({"sum", "count", "avg", "min", "max", "collect_list",
                         "collect_set", "group_concat", "stddev", "variance"})

_AGG_RE = re.compile(
    r"\b(?:" + "|".join(_AGG_FUNCS) + r")\s*\(", re.IGNORECASE,
)

_ON_BLOCK_RE = re.compile(
    r"\bON\s+(.*?)(?=\bJOIN\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|\bHAVING\b|$)",
    re.IGNORECASE | re.DOTALL,
)
_EQ_PAIR_RE = re.compile(r"([\w.]+)\s*=\s*([\w.]+)")

_WHERE_BLOCK_RE = re.compile(
    r"\bWHERE\s+(.*?)(?:\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|\bHAVING\b|$)",
    re.IGNORECASE | re.DOTALL,
)

_GROUPBY_BLOCK_RE = re.compile(
    r"\bGROUP\s+BY\s+(.*?)(?:\bHAVING\b|\bORDER\s+BY\b|\bLIMIT\b|$)",
    re.IGNORECASE | re.DOTALL,
)

_SELECT_FROM_RE = re.compile(
    r"\bSELECT\s+(.*?)\s+FROM\b", re.IGNORECASE | re.DOTALL,
)

def _parse_table_aliases(cleaned: str) -> dict[str, str]:
    """Extract table alias→real name mapping from FROM/JOIN clauses."""
    aliases: dict[str, str] = {}
    for m in re.finditer(
        r"\b(?:FROM|JOIN)\s+(\w+(?:\.\w+)?)\s+(?:AS\s+)?(\w+)\b",
        cleaned, re.IGNORECASE,
    ):
        table, alias = m.group(1).lower(), m.group(2).lower()
        if alias not in _SQL_KEYWORDS:
            aliases[alias] = table
    return aliases


def _resolve_table(col_or_ref: str, aliases: dict[str, str],
                   store: SchemaStore | None,
                   source_tables: list[str]) -> tuple[str, str]:
    """Resolve a column reference to (table, column).

    Handles:
      - qualified: ``t.col`` or ``alias.col``
      - unqualified: ``col`` → search source tables in SchemaStore
    """
    if "." in col_or_ref:
        parts = col_or_ref.split(".", 1)
        table_ref = parts[0].lower()
        col = parts[1].lower()
        real = aliases.get(table_ref, table_ref)
        return real, col

    col = col_or_ref.lower()
    if store:
        for tname in source_tables:
            tb = store.get(tname)
            if tb is None:
                for t in store.tables:
                    if t.name.lower() == tname:
                        tb = t
                        break
            if tb and tb.find_column(col):
                return tname, col
    return "", col


def _split_select_items(select_body: str) -> list[str]:
    """Split a SELECT projection by commas, respecting parentheses."""
    items: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in select_body:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        items.append(tail)
    return items


def _parse_output_columns(
    cleaned: str,
    aliases: dict[str, str],
    store: SchemaStore | None,
    source_tables: list[str],
) -> list[ColumnLineage]:
    """Parse SELECT projection into ColumnLineage entries."""
    m = _SELECT_FROM_RE.search(cleaned)
    if not m:
        return []

    select_body = m.group(1).strip()
    if select_body == "*":
        return [ColumnLineage(output_name="*", expression="*")]

    items = _split_select_items(select_body)
    columns: list[ColumnLineage] = []

    for item in items:
        if not item:
            continue
        # Extract alias: "expr AS alias" or "expr alias" (where alias is last word)
        as_match = re.match(r"(.+?)\s+AS\s+(\w+)\s*$", item, re.IGNORECASE)
        if as_match:
            expr = as_match.group(1).strip()
            out_name = as_match.group(2).strip()
        else:
            # Try "expr word" where word is last token and not a keyword
            parts = item.rsplit(None, 1)
            if len(parts) == 2 and re.match(r"^\w+$", parts[1]) and parts[1].lower() not in _SQL_KEYWORDS:
                expr = parts[0].strip()
                out_name = parts[1].strip()
            else:
                expr = item
                # Use the column name itself as output name
                col_match = re.search(r"(\w+)\s*$", item)
                out_name = col_match.group(1) if col_match else item

        is_agg = bool(_AGG_RE.search(expr))

        # Try to resolve source
        source_table = ""
        source_column = ""
        if not is_agg:
            col_ref = expr.strip()
            if re.match(r"^[\w.]+$", col_ref):
                source_table, source_column = _resolve_table(
                    col_ref, aliases, store, source_tables,
                )
        else:
            # Extract column from inside aggregation: SUM(t.col) → t.col
            inner = re.search(r"\(\s*([\w.]+)\s*\)", expr)
            if inner:
                ref = inner.group(1)
                if ref != "*":
                    source_table, source_column = _resolve_table(
                        ref, aliases, store, source_tables,
                    )

        columns.append(ColumnLineage(
            output_name=out_name,
            source_table=source_table,
            source_column=source_column,
            expression=expr,
            is_aggregation=is_agg,
        ))

    return columns


def _parse_joins(cleaned: str, aliases: dict[str, str]) -> list[str]:
    """Extract join conditions as 'table.col = table.col' strings."""
    joins: list[str] = []
    for block_m in _ON_BLOCK_RE.finditer(cleaned):
        on_block = block_m.group(1)
        for m in _EQ_PAIR_RE.finditer(on_block):
            left, right = m.group(1), m.group(2)
            parts_l = left.split(".", 1)
            parts_r = right.split(".", 1)
            if len(parts_l) == 2:
                real_l = aliases.get(parts_l[0].lower(), parts_l[0])
                left = f"{real_l}.{parts_l[1]}"
            if len(parts_r) == 2:
                real_r = aliases.get(parts_r[0].lower(), parts_r[0])
                right = f"{real_r}.{parts_r[1]}"
            joins.append(f"{left} = {right}")
    return joins


def _parse_filters(cleaned: str) -> list[str]:
    """Extract WHERE clause fragments."""
    m = _WHERE_BLOCK_RE.search(cleaned)
    if not m:
        return []
    block = m.group(1).strip()
    parts = re.split(r"\s+AND\s+|\s+OR\s+", block, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _parse_group_by(cleaned: str) -> list[str]:
    """Extract GROUP BY column list."""
    m = _GROUPBY_BLOCK_RE.search(cleaned)
    if not m:
        return []
    block = m.group(1).strip()
    return [c.strip() for c in block.split(",") if c.strip()]


def trace_lineage(sql: str, store: SchemaStore | None = None) -> SqlLineage:
    """Parse SQL and build a best-effort lineage trace."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        return SqlLineage()

    cleaned = _strip_literals_and_comments(stripped)

    source_tables = extract_tables(sql)
    cte_names = _extract_cte_names(cleaned)
    real_tables = [t for t in source_tables if t.lower() not in cte_names]

    aliases = _parse_table_aliases(cleaned)
    output_columns = _parse_output_columns(cleaned, aliases, store, real_tables)
    joins = _parse_joins(cleaned, aliases)
    filters = _parse_filters(cleaned)
    group_by = _parse_group_by(cleaned)

    return SqlLineage(
        source_tables=real_tables,
        output_columns=output_columns,
        joins=joins,
        filters=filters,
        group_by=group_by,
        cte_names=cte_names,
    )
