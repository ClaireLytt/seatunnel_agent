"""Deterministic manual-check rules for dialect translation.

Each rule inspects the parsed source AST and flags patterns that sqlglot
translates syntactically but that still deserve a human look on the target
engine (unknown UDFs, storage clauses, bucketing hints, …).

Rules are pure functions over the AST — easy to unit-test, no I/O.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlglot import exp

if TYPE_CHECKING:  # pragma: no cover — import cycle guard
    from .transpiler import Issue

# Targets whose table/storage DDL differs enough from Hive/Spark that the
# storage & distribution clauses always need a human pass (clickhouse's
# ENGINE/ORDER BY model included).
_MPP_TARGETS = {"doris", "starrocks", "clickhouse"}


def _snippet(node: exp.Expression, max_len: int = 60) -> str:
    one = " ".join(node.sql().split())
    return one if len(one) <= max_len else one[:max_len] + "…"


def manual_checks(
    ast: exp.Expression, stmt_line: int, *, src: str, dst: str
) -> list["Issue"]:
    from .transpiler import Issue  # local import to avoid a cycle

    issues: list[Issue] = []

    # ── unknown functions (exp.Anonymous = sqlglot has no mapping) ──
    seen: set[str] = set()
    for fn in ast.find_all(exp.Anonymous):
        name = (fn.name or "").lower()
        if not name or name in seen:
            continue
        seen.add(name)
        issues.append(Issue(
            level="warn", kind="unknown_function", line=stmt_line,
            snippet=_snippet(fn), params={"func": fn.name},
        ))

    if dst not in _MPP_TARGETS:
        # hive/spark targets keep DISTRIBUTE BY / LATERAL VIEW / STORED AS
        # semantics — only the UDF rule applies.
        return issues

    # ── DISTRIBUTE BY / CLUSTER BY / SORT BY (Hive write-side hints) ──
    for select in ast.find_all(exp.Select):
        for arg, clause in (("distribute", "DISTRIBUTE BY"),
                            ("cluster", "CLUSTER BY"),
                            ("sort", "SORT BY")):
            node = select.args.get(arg)
            if node is not None:
                issues.append(Issue(
                    level="info", kind="write_hint", line=stmt_line,
                    snippet=_snippet(node), params={"clause": clause},
                ))

    # ── LATERAL VIEW explode(...) — table-function support differs ──
    if any(True for _ in ast.find_all(exp.Lateral)):
        issues.append(Issue(
            level="info", kind="lateral_view", line=stmt_line,
            snippet=_snippet(next(ast.find_all(exp.Lateral))),
        ))

    # ── INSERT ... PARTITION (dt=...) — partition write syntax differs ──
    if isinstance(ast, exp.Insert) and any(
            True for _ in ast.find_all(exp.Partition)):
        issues.append(Issue(
            level="info", kind="insert_partition", line=stmt_line,
            snippet=_snippet(next(ast.find_all(exp.Partition))),
        ))

    # ── CREATE TABLE storage clauses (STORED AS / TBLPROPERTIES / ROW FORMAT)
    if isinstance(ast, exp.Create):
        props = ast.args.get("properties")
        clauses: list[str] = []
        for p in (props.expressions if props else []):
            if isinstance(p, exp.FileFormatProperty):
                clauses.append("STORED AS")
            elif isinstance(p, (exp.RowFormatDelimitedProperty,
                                exp.RowFormatSerdeProperty)):
                clauses.append("ROW FORMAT")
            elif isinstance(p, exp.Property):
                clauses.append("TBLPROPERTIES")
        if clauses:
            issues.append(Issue(
                level="warn", kind="storage_clause", line=stmt_line,
                snippet=_snippet(ast.this),
                params={"clauses": ", ".join(dict.fromkeys(clauses))},
            ))

    return issues
