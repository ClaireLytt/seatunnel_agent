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


def parse_profile_result(
    table_name: str,
    columns: list[dict[str, str]],
    row: tuple | list,
) -> TableProfile:
    """Parse the single result row from a profile SQL query."""
    values = list(row)
    row_count = values[0] if values else 0
    profiles: list[ColumnProfile] = []
    cols = columns[:_MAX_PROFILE_COLUMNS]
    idx = 1
    for c in cols:
        if idx + 3 >= len(values):
            break
        non_null = values[idx]
        distinct = values[idx + 1]
        min_val = values[idx + 2]
        max_val = values[idx + 3]
        null_count = (row_count or 0) - (non_null or 0)
        profiles.append(ColumnProfile(
            name=c["name"],
            dtype=c.get("type", ""),
            total_count=row_count or 0,
            null_count=null_count,
            distinct_count=distinct or 0,
            min_value=min_val,
            max_value=max_val,
        ))
        idx += 4
    return TableProfile(
        table_name=table_name,
        row_count=row_count or 0,
        columns=profiles,
    )
