"""Deterministic semantic diff between two versions of pipeline SQL.

``git diff`` shows a reformatted query as a wall of changes and a
re-aliased join as nothing at all; this differ parses both versions
(sqlglot, the lineage stack — nothing executed), matches statements by
their write target, and reports what actually changed in meaning:

* breaking — a write statement disappeared, an output column was
  dropped, or INSERT INTO/OVERWRITE flipped;
* risk — an output column's expression changed, a filter (WHERE) or
  aggregation (GROUP BY/HAVING) changed, a source table joined in or
  dropped out;
* info — a new statement or output column, pure re-formatting never
  counts.

Statements without a write target (bare SELECTs) pair up by position.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["SqlDiffFinding", "SqlDiffReport", "diff_sql",
           "statement_shapes"]

SEVERITIES = ("breaking", "risk", "info")

KIND_SEVERITY = {
    "statement_removed": "breaking",
    "column_removed": "breaking",
    "write_mode_changed": "breaking",
    "column_expr_changed": "risk",
    "filter_changed": "risk",
    "aggregation_changed": "risk",
    "source_added": "risk",
    "source_removed": "risk",
    "statement_added": "info",
    "column_added": "info",
}


@dataclass
class SqlDiffFinding:
    kind: str           # one of KIND_SEVERITY
    severity: str       # breaking | risk | info
    target: str         # the write target (or <select#n>)
    subject: str = ""   # column / table / clause involved
    old: str = ""
    new: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity,
                "target": self.target, "subject": self.subject,
                "old": self.old, "new": self.new}


@dataclass
class SqlDiffReport:
    dialect: str
    statements_old: int = 0
    statements_new: int = 0
    findings: list[SqlDiffFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def identical(self) -> bool:
        return not self.findings

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings, SEVERITIES)

    def to_dict(self) -> dict[str, Any]:
        return {"dialect": self.dialect,
                "statements_old": self.statements_old,
                "statements_new": self.statements_new,
                "identical": self.identical,
                "counts": self.counts(),
                "findings": [f.to_dict() for f in self.findings],
                "warnings": list(self.warnings)}


# ---------------------------------------------------------------------------
# parsing into per-statement shapes
# ---------------------------------------------------------------------------

@dataclass
class _Shape:
    target: str                      # write target or <select#n>
    write_mode: str = ""             # insert | overwrite | create | ""
    columns: dict[str, str] = field(default_factory=dict)   # name -> expr
    sources: dict[str, str] = field(default_factory=dict)   # table -> join
    where: str = ""
    aggregation: str = ""            # GROUP BY + HAVING, canonical


def _canon(node, read) -> str:
    if node is None:
        return ""
    return " ".join(node.sql(dialect=read, comments=False).split()).lower()


def _table_name(t) -> str:
    parts = [p for p in (t.catalog, t.db, t.name) if p]
    return ".".join(parts).lower()


def _statement_shapes(sql_text: str, read) -> tuple[list[_Shape], list[str]]:
    import sqlglot
    from sqlglot import exp

    try:
        trees = sqlglot.parse(sql_text, read=read)
    except sqlglot.errors.ParseError as exc:
        raise ValueError(f"SQL 解析失败 / cannot parse: {str(exc)[:200]}")

    shapes: list[_Shape] = []
    warnings: list[str] = []
    select_n = 0
    for tree in trees:
        if tree is None:
            continue
        target, mode = "", ""
        if isinstance(tree, exp.Insert):
            t = tree.find(exp.Table)
            target = _table_name(t) if t is not None else ""
            mode = "overwrite" if tree.args.get("overwrite") else "insert"
        elif isinstance(tree, exp.Create):
            t = tree.find(exp.Table)
            target = _table_name(t) if t is not None else ""
            mode = "create"
        query = tree.find(exp.Select)
        if query is None:
            if not target:
                continue
            shapes.append(_Shape(target=target, write_mode=mode))
            continue
        if not target:
            select_n += 1
            target = f"<select#{select_n}>"
        shape = _Shape(target=target, write_mode=mode)
        for e in query.expressions:
            if isinstance(e, exp.Star):
                shape.columns["*"] = "*"
                warnings.append(f"{target}: SELECT * — 列级变化不可见 / "
                                "column-level changes invisible")
                continue
            name = (e.alias_or_name or _canon(e, read)).lower()
            shape.columns[name] = _canon(
                e.this if isinstance(e, exp.Alias) else e, read)
        # sqlglot names the arg "from" or "from_" depending on version
        from_ = query.args.get("from") or query.args.get("from_")
        if from_ is not None:
            for t in from_.find_all(exp.Table):
                shape.sources[_table_name(t)] = "from"
        for j in query.args.get("joins") or []:
            t = j.find(exp.Table)
            if t is not None:
                kind = (j.kind or j.side or "join").lower()
                shape.sources[_table_name(t)] = kind
        shape.where = _canon(query.args.get("where"), read)
        agg = [_canon(query.args.get("group"), read),
               _canon(query.args.get("having"), read)]
        shape.aggregation = " ".join(p for p in agg if p)
        shapes.append(shape)
    return shapes, warnings


def statement_shapes(sql_text: str, dialect: str = "hive",
                     ) -> tuple[list[_Shape], list[str]]:
    """Public seam: per-statement semantic shapes (dup_pipeline reuses
    the same parse instead of growing its own)."""
    from seatunnel_agent.agents.data.data_lineage.sqlglot_lineage import (
        resolve_sqlglot_dialect,
    )

    if not (sql_text or "").strip():
        raise ValueError("SQL must not be empty")
    return _statement_shapes(sql_text, resolve_sqlglot_dialect(dialect))


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------

def _diff_pair(old: _Shape, new: _Shape, add) -> None:
    t = new.target
    if old.write_mode != new.write_mode and old.write_mode and new.write_mode:
        add("write_mode_changed", t, "write mode",
            old.write_mode, new.write_mode)
    for name, expr in old.columns.items():
        if name not in new.columns:
            add("column_removed", t, name, expr, "")
        elif new.columns[name] != expr:
            add("column_expr_changed", t, name, expr, new.columns[name])
    for name, expr in new.columns.items():
        if name not in old.columns:
            add("column_added", t, name, "", expr)
    for src in old.sources:
        if src not in new.sources:
            add("source_removed", t, src, old.sources[src], "")
    for src in new.sources:
        if src not in old.sources:
            add("source_added", t, src, "", new.sources[src])
    if old.where != new.where:
        add("filter_changed", t, "WHERE", old.where or "-",
            new.where or "-")
    if old.aggregation != new.aggregation:
        add("aggregation_changed", t, "GROUP BY/HAVING",
            old.aggregation or "-", new.aggregation or "-")


def diff_sql(old_sql: str, new_sql: str,
             dialect: str = "hive") -> SqlDiffReport:
    """Two pipeline SQL scripts → graded semantic differences."""
    from seatunnel_agent.agents.data.data_lineage.sqlglot_lineage import (
        resolve_sqlglot_dialect,
    )

    if not (old_sql or "").strip():
        raise ValueError("old SQL must not be empty")
    if not (new_sql or "").strip():
        raise ValueError("new SQL must not be empty")
    read = resolve_sqlglot_dialect(dialect)
    old_shapes, w_old = _statement_shapes(old_sql, read)
    new_shapes, w_new = _statement_shapes(new_sql, read)
    if not old_shapes:
        raise ValueError("old SQL has no statements to compare")
    if not new_shapes:
        raise ValueError("new SQL has no statements to compare")

    report = SqlDiffReport(dialect=dialect,
                           statements_old=len(old_shapes),
                           statements_new=len(new_shapes),
                           warnings=sorted(set(w_old + w_new)))

    def add(kind: str, target: str, subject: str,
            old: str, new: str) -> None:
        report.findings.append(SqlDiffFinding(
            kind=kind, severity=KIND_SEVERITY[kind], target=target,
            subject=subject, old=old, new=new))

    old_by = {s.target: s for s in old_shapes}
    new_by = {s.target: s for s in new_shapes}
    for target, old in old_by.items():
        if target not in new_by:
            add("statement_removed", target, "", old.write_mode, "")
            continue
        _diff_pair(old, new_by[target], add)
    for target, new in new_by.items():
        if target not in old_by:
            add("statement_added", target, "", "", new.write_mode)
    return report
