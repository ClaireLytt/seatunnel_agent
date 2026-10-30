"""Deterministic index / partition / bucketing advisor.

Input: a query workload (a directory of ``*.sql`` or pasted
multi-statement text) and optionally the tables' DDL.  Each statement
is parsed with sqlglot; per table-column the advisor counts how often
it appears as

* an equality filter (``col = literal`` / ``col IN (...)``),
* a range filter (``>`` ``<`` ``BETWEEN``),
* a join key (``a.col = b.col``), or
* a GROUP BY key,

then recommends per table:

* **partition column** — the most-filtered equality column whose name
  or DDL type looks date-like (``dt``, ``*_date``, date/timestamp);
* **bucketing column** — the hottest join key (``CLUSTERED BY``);
* **composite index** (MySQL/Doris-style) — equality columns by
  frequency, the hottest range column last.

Every recommendation carries the number of statements it serves and a
ready-to-adapt DDL fragment.  Statements sqlglot cannot parse are
skipped and reported — never guessed at.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

_DATE_NAME_RE = re.compile(
    r"(^|_)(dt|date|day|ds|pt|hour|month)($|_)|_(at|time)$", re.IGNORECASE)
_DATE_TYPE_RE = re.compile(r"date|timestamp", re.IGNORECASE)
_CREATE_COL_RE = re.compile(r"^\s*`?(\w+)`?\s+(\w+)", re.MULTILINE)
_CREATE_TABLE_RE = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?`?([\w.]+)`?\s*\((.*?)\)\s*"
    r"(?:engine|partitioned|stored|comment|with|distributed|;|$)",
    re.IGNORECASE | re.DOTALL)


@dataclass
class ColumnStats:
    eq: int = 0
    range: int = 0
    join: int = 0
    group: int = 0

    @property
    def total(self) -> int:
        return self.eq + self.range + self.join + self.group

    def to_dict(self) -> dict[str, int]:
        return {"eq": self.eq, "range": self.range, "join": self.join,
                "group": self.group}


@dataclass
class TableAdvice:
    table: str
    statements: int                 # statements touching this table
    columns: dict[str, ColumnStats] = field(default_factory=dict)
    partition_col: str | None = None
    bucket_col: str | None = None
    index_cols: list[str] = field(default_factory=list)
    ddl: list[str] = field(default_factory=list)  # ready-to-adapt fragments

    def to_dict(self) -> dict[str, Any]:
        return {"table": self.table, "statements": self.statements,
                "columns": {c: s.to_dict() for c, s in self.columns.items()},
                "partition_col": self.partition_col,
                "bucket_col": self.bucket_col,
                "index_cols": list(self.index_cols),
                "ddl": list(self.ddl)}


@dataclass
class WorkloadAdvice:
    tables: list[TableAdvice] = field(default_factory=list)
    statements: int = 0
    skipped: list[str] = field(default_factory=list)  # unparseable heads

    def to_dict(self) -> dict[str, Any]:
        return {"tables": [t.to_dict() for t in self.tables],
                "statements": self.statements,
                "skipped": list(self.skipped)}


def parse_ddl_types(ddl_text: str) -> dict[str, dict[str, str]]:
    """CREATE TABLE text → {table: {column: type}} (regex, best-effort)."""
    out: dict[str, dict[str, str]] = {}
    for m in _CREATE_TABLE_RE.finditer(ddl_text or ""):
        cols = {c.lower(): t.lower()
                for c, t in _CREATE_COL_RE.findall(m.group(2))}
        out[m.group(1).lower()] = cols
    return out


def _split(text: str) -> list[str]:
    from seatunnel_agent.agents.data.sql_review.linter import (
        split_statements,
    )

    return [stmt for _, stmt in split_statements(text) if stmt.strip()]


def _alias_map(stmt: Any) -> dict[str, str]:
    from sqlglot import exp

    out: dict[str, str] = {}
    for t in stmt.find_all(exp.Table):
        name = ".".join(p for p in (t.db, t.name) if p).lower()
        out[(t.alias_or_name or t.name).lower()] = name
        out.setdefault(t.name.lower(), name)
    return out


def _resolve(col: Any, aliases: dict[str, str]) -> tuple[str, str] | None:
    table_ref = (col.table or "").lower()
    name = col.name.lower()
    if table_ref:
        table = aliases.get(table_ref)
        return (table, name) if table else None
    if len(set(aliases.values())) == 1:
        return next(iter(set(aliases.values()))), name
    return None  # ambiguous bare column in a multi-table statement


def analyze_workload(sql_text: str,
                     dialect: str = "hive") -> WorkloadAdvice:
    import sqlglot
    from sqlglot import exp

    statements = _split(sql_text)
    if not statements:
        raise ValueError("no SQL statements found")
    advice = WorkloadAdvice(statements=len(statements))
    stats: dict[str, dict[str, ColumnStats]] = defaultdict(
        lambda: defaultdict(ColumnStats))
    touched: Counter[str] = Counter()

    for raw in statements:
        try:
            stmt = sqlglot.parse_one(raw, read=dialect)
        except Exception:
            advice.skipped.append(raw.strip().splitlines()[0][:60])
            continue
        aliases = _alias_map(stmt)
        for table in set(aliases.values()):
            touched[table] += 1

        def bump(col: Any, kind: str) -> None:
            resolved = _resolve(col, aliases)
            if resolved is None:
                return
            table, name = resolved
            setattr(stats[table][name], kind,
                    getattr(stats[table][name], kind) + 1)

        for eq in stmt.find_all(exp.EQ):
            left, right = eq.left, eq.right
            if isinstance(left, exp.Column) and isinstance(right, exp.Column):
                bump(left, "join")
                bump(right, "join")
            elif isinstance(left, exp.Column):
                bump(left, "eq")
            elif isinstance(right, exp.Column):
                bump(right, "eq")
        for in_ in stmt.find_all(exp.In):
            if isinstance(in_.this, exp.Column):
                bump(in_.this, "eq")
        for node in stmt.find_all(exp.GT, exp.GTE, exp.LT, exp.LTE):
            if isinstance(node.this, exp.Column):
                bump(node.this, "range")
        for between in stmt.find_all(exp.Between):
            if isinstance(between.this, exp.Column):
                bump(between.this, "range")
        group = stmt.find(exp.Group)
        if group:
            for col in group.find_all(exp.Column):
                bump(col, "group")

    for table in sorted(stats):
        advice.tables.append(TableAdvice(
            table=table, statements=touched.get(table, 0),
            columns=dict(sorted(stats[table].items(),
                                key=lambda kv: -kv[1].total))))
    if not advice.tables and not advice.skipped:
        raise ValueError("no table references recognized in the workload")
    return advice


def recommend(advice: WorkloadAdvice,
              ddl_text: str = "") -> WorkloadAdvice:
    """Attach partition / bucket / index picks and DDL fragments."""
    types = parse_ddl_types(ddl_text)
    for t in advice.tables:
        cols = t.columns
        table_types = types.get(t.table, {})

        def date_like(name: str) -> bool:
            return bool(_DATE_NAME_RE.search(name)
                        or _DATE_TYPE_RE.search(table_types.get(name, "")))

        partition_cands = sorted(
            (name for name, s in cols.items() if s.eq and date_like(name)),
            key=lambda n: (-cols[n].eq, -cols[n].total, n))
        if partition_cands:
            t.partition_col = partition_cands[0]
            t.ddl.append(f"PARTITIONED BY ({t.partition_col})")
        join_cands = sorted(
            (name for name, s in cols.items() if s.join),
            key=lambda n: (-cols[n].join, -cols[n].total, n))
        if join_cands:
            t.bucket_col = join_cands[0]
            t.ddl.append(f"CLUSTERED BY ({t.bucket_col}) INTO 32 BUCKETS")
        eq_cols = sorted((name for name, s in cols.items()
                          if s.eq and name != t.partition_col),
                         key=lambda n: (-cols[n].eq, n))
        range_cols = sorted((name for name, s in cols.items() if s.range),
                            key=lambda n: (-cols[n].range, n))
        index = eq_cols[:2] + [c for c in range_cols[:1]
                               if c not in eq_cols[:2]]
        if index:
            t.index_cols = index
            short = t.table.rsplit(".", 1)[-1]
            t.ddl.append(f"CREATE INDEX idx_{short}_{'_'.join(index)} "
                         f"ON {t.table} ({', '.join(index)})")
    return advice
