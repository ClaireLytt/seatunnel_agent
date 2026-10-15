"""Data profiling — generate stats SQL and parse results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_MAX_PROFILE_COLUMNS = 20

_BACKTICK_DIALECTS = frozenset({
    "hive", "mysql", "sparksql", "flinksql", "clickhouse", "doris", "sqlite",
})


def quote_identifier(name: str, dialect: str = "hive") -> str:
    """Quote an identifier for *dialect*, stripping embedded quote chars."""
    safe = name.replace("`", "").replace('"', "").replace("[", "").replace("]", "")
    if dialect in _BACKTICK_DIALECTS:
        return f"`{safe}`"
    if dialect == "sqlserver":
        return f"[{safe}]"
    # postgresql and other ANSI dialects
    return f'"{safe}"'


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    total_count: int = 0
    null_count: int = 0
    distinct_count: int = 0
    min_value: Any = None
    max_value: Any = None


@dataclass
class TableProfile:
    table_name: str
    row_count: int = 0
    columns: list[ColumnProfile] = field(default_factory=list)


def build_profile_sql(table_name: str, columns: list[dict[str, str]],
                      dialect: str = "hive") -> str:
    """Generate a single SQL query that profiles up to 20 columns.

    Each column produces: COUNT(col), COUNT(DISTINCT col), MIN(col), MAX(col).
    Always starts with COUNT(*) for row count. Identifiers are quoted per
    *dialect* (backticks for hive/mysql-family, [..] for sqlserver,
    double quotes for postgresql).
    """
    q = lambda n: quote_identifier(n, dialect)
    cols = columns[:_MAX_PROFILE_COLUMNS]
    parts = ["COUNT(*) AS _row_count_"]
    for c in cols:
        name = c["name"]
        parts.append(f"COUNT({q(name)}) AS {q(name + '__non_null')}")
        parts.append(f"COUNT(DISTINCT {q(name)}) AS {q(name + '__distinct')}")
        parts.append(f"MIN({q(name)}) AS {q(name + '__min')}")
        parts.append(f"MAX({q(name)}) AS {q(name + '__max')}")
    select = ",\n  ".join(parts)
    return f"SELECT\n  {select}\nFROM {q(table_name)}"


