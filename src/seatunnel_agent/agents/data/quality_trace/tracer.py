"""Deterministic quality root-cause tracing over SQL lineage.

Input is a quality event (table + optional column + symptom) and the SQL
scripts that build the pipeline.  The lineage graph comes from the
data_lineage parser (reused, not reimplemented); this module walks the
ancestors of the polluted table and scores every one as a suspect —
closer ancestors score higher, ancestors reached by a column-level taint
path higher still, and transforming expressions (aggregations, CASE,
arithmetic) along that path are reported as the mutation points.  Each
top suspect gets a copy-ready verification SQL.  No database connection.
"""

from __future__ import annotations

import tempfile
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from seatunnel_agent.agents.data.data_lineage import (
    LineageGraph,
    from_sql_files,
    norm_table,
)

__all__ = ["Suspect", "TraceResult", "build_graph_from_sql", "trace_quality"]

_MAX_DEPTH = 5


@dataclass
class Suspect:
    table: str
    distance: int
    score: float
    column_hits: list[str] = field(default_factory=list)
    expressions: list[str] = field(default_factory=list)
    verify_sql: str = ""

    def to_dict(self) -> dict:
        return {"table": self.table, "distance": self.distance,
                "score": round(self.score, 1),
                "column_hits": self.column_hits,
                "expressions": self.expressions,
                "verify_sql": self.verify_sql}


@dataclass
class TraceResult:
    table: str
    column: str
    symptom: str
    warnings: list[str]
    upstream_tables: int
    suspects: list[Suspect]

    def to_dict(self) -> dict:
        return {"table": self.table, "column": self.column,
                "symptom": self.symptom, "warnings": self.warnings,
                "upstream_tables": self.upstream_tables,
                "suspects": [s.to_dict() for s in self.suspects]}


def build_graph_from_sql(sql_text: str,
                         dialect: str = "hive") -> tuple[LineageGraph, list[str]]:
    """Pasted SQL script(s) → lineage graph via the data_lineage parser.

    The parser's file cache is pointed at a throwaway directory so pasted
    text never pollutes the repo's ``logs/``.
    """
    if not (sql_text or "").strip():
        raise ValueError("empty SQL / SQL 为空")
    with tempfile.TemporaryDirectory(prefix="qtrace_") as tmp:
        sql_path = Path(tmp) / "pipeline.sql"
        sql_path.write_text(sql_text, encoding="utf-8")
        graph, warnings = from_sql_files([sql_path], cache_base=tmp,
                                         dialect=dialect)
    return graph, warnings


def _taint_columns(graph: LineageGraph, table: str,
                   column: str) -> tuple[dict[str, set[str]], dict[str, list[str]]]:
    """Walk column edges upstream from (table, column).

    Returns {table: tainted columns} and {table: expressions seen on the
    taint path into that table's columns}.
    """
    tainted: dict[str, set[str]] = {table: {column}}
    exprs: dict[str, list[str]] = {}
    queue: deque[tuple[str, str]] = deque([(table, column)])
    visited = {(table, column)}
    while queue:
        tbl, col = queue.popleft()
        for edge in graph.column_up.get((tbl, col), ()):
            key = (edge.src_table, edge.src_column)
            expr = (edge.expression or "").strip()
            if expr and expr.lower() != edge.src_column:
                bucket = exprs.setdefault(edge.src_table, [])
                if expr not in bucket:
                    bucket.append(expr)
            if key in visited:
                continue
            visited.add(key)
            tainted.setdefault(edge.src_table, set()).add(edge.src_column)
            queue.append(key)
    return tainted, exprs


def _verify_sql(table: str, columns: list[str]) -> str:
    if columns:
        col = columns[0]
        return (f"SELECT COUNT(*) AS cnt, "
                f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END) AS "
                f"null_cnt, MIN({col}) AS min_v, MAX({col}) AS max_v "
                f"FROM {table};")
    return f"SELECT COUNT(*) AS cnt FROM {table};"


def trace_quality(graph: LineageGraph, warnings: list[str], table: str,
                  column: str = "", symptom: str = "",
                  depth: int = _MAX_DEPTH) -> TraceResult:
    root = norm_table(table)
    chain = graph.upstream_of(root, depth=depth)
    if chain.missing_root:
        raise ValueError(f"table '{table}' not found in the SQL lineage / "
                         f"表不在血缘里")
    root = chain.root
    col = (column or "").strip().lower()
    tainted: dict[str, set[str]] = {}
    exprs: dict[str, list[str]] = {}
    if col:
        tainted, exprs = _taint_columns(graph, root, col)

    suspects: list[Suspect] = []
    for name, d in chain.depth_of.items():
        if d >= 0:      # the root itself; upstream depths are negative
            continue
        dist = -d
        hits = sorted(tainted.get(name, ()))
        score = 100.0 / (1 + dist)
        if col:
            # when a column is named, ancestors off the taint path are
            # weak suspects; on-path ancestors get the column bonus
            score = score * (0.4 if not hits else 1.0) + (40.0 if hits else 0)
        if exprs.get(name):
            score += 10.0
        suspects.append(Suspect(
            table=name, distance=dist, score=score,
            column_hits=hits, expressions=exprs.get(name, [])[:3],
            verify_sql=_verify_sql(name, hits)))
    suspects.sort(key=lambda s: (-s.score, s.distance, s.table))
    return TraceResult(table=root, column=col, symptom=symptom.strip(),
                       warnings=list(warnings),
                       upstream_tables=len(suspects), suspects=suspects)
