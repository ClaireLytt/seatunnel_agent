"""Deterministic data-dictionary skeleton from DDL and SQL usage.

The catalog parser is reused from asset_search (JSON asset list or
Hive-style DDL).  Every column gets an inferred role from its name shape
— key / time / measure / flag / dimension — plus its usage counts mined
from the optional SQL workload (filter, join, group-by appearances).
The result is a complete dictionary skeleton whose description cells say
what can be said deterministically (role, comment, usage); the optional
LLM pass drafts the business descriptions on top of the skeleton, never
instead of it.  No database connection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from seatunnel_agent.agents.data.asset_search import Asset, parse_catalog

__all__ = ["DictEntry", "DictResult", "TableDict", "generate_dict"]

_ROLE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("key", re.compile(r"(^id$|_id$|_no$|_code$|^pk_|_key$)")),
    ("time", re.compile(r"(date|time|_at$|_ts$|^ts$|month|week|hour)")),
    ("flag", re.compile(r"(^is_|_flag$|^has_|status|state|type$)")),
    ("measure", re.compile(
        r"(amount|amt|gmv|price|fee|cnt|count|qty|num$|rate|ratio|pct|"
        r"total|sum)")),
)


@dataclass
class DictEntry:
    name: str
    role: str
    comment: str = ""
    filter_uses: int = 0
    join_uses: int = 0
    group_uses: int = 0

    def to_dict(self) -> dict:
        return {"name": self.name, "role": self.role,
                "comment": self.comment,
                "filter_uses": self.filter_uses,
                "join_uses": self.join_uses,
                "group_uses": self.group_uses}


@dataclass
class TableDict:
    table: str
    comment: str
    entries: list[DictEntry] = field(default_factory=list)

    @property
    def comment_coverage(self) -> float:
        if not self.entries:
            return 0.0
        return 100.0 * sum(1 for e in self.entries if e.comment) / len(
            self.entries)

    def to_dict(self) -> dict:
        return {"table": self.table, "comment": self.comment,
                "comment_coverage": round(self.comment_coverage, 1),
                "entries": [e.to_dict() for e in self.entries]}


@dataclass
class DictResult:
    tables: list[TableDict]

    def to_dict(self) -> dict:
        return {"tables": [t.to_dict() for t in self.tables]}


def _role_of(name: str) -> str:
    low = name.lower()
    for role, pat in _ROLE_RULES:
        if pat.search(low):
            return role
    return "dimension"


_WHERE_RE = re.compile(r"\bWHERE\b(.*?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|;|$)",
                       re.IGNORECASE | re.DOTALL)
_ON_RE = re.compile(r"\bON\b(.*?)(?:\bWHERE\b|\bJOIN\b|\bGROUP\b|;|$)",
                    re.IGNORECASE | re.DOTALL)
_GROUP_RE = re.compile(r"\bGROUP\s+BY\b(.*?)(?:\bORDER\b|\bHAVING\b|"
                       r"\bLIMIT\b|;|$)", re.IGNORECASE | re.DOTALL)


def _usage_counts(sql: str, column: str) -> tuple[int, int, int]:
    if not sql:
        return 0, 0, 0
    word = re.compile(rf"\b{re.escape(column)}\b", re.IGNORECASE)
    f = sum(len(word.findall(m.group(1))) for m in _WHERE_RE.finditer(sql))
    j = sum(len(word.findall(m.group(1))) for m in _ON_RE.finditer(sql))
    g = sum(len(word.findall(m.group(1))) for m in _GROUP_RE.finditer(sql))
    return f, j, g


def generate_dict(catalog_text: str, sql_text: str = "") -> DictResult:
    assets: list[Asset] = parse_catalog(catalog_text)
    sql = sql_text or ""
    tables: list[TableDict] = []
    for a in assets:
        td = TableDict(table=a.table, comment=a.comment)
        for col in a.columns:
            name = col["name"]
            f, j, g = _usage_counts(sql, name)
            td.entries.append(DictEntry(
                name=name, role=_role_of(name),
                comment=col.get("comment") or "",
                filter_uses=f, join_uses=j, group_uses=g))
        tables.append(td)
    return DictResult(tables=tables)
