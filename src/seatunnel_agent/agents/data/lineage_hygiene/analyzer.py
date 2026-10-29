"""Deterministic hygiene core over the shared lineage graph."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from seatunnel_agent.agents.data.data_lineage.loaders import from_sql_files
from seatunnel_agent.agents.data.pii_scan.scanner import collect_columns_from_ddl


@dataclass
class HygieneItem:
    kind: str                # orphan_output | dead_column | dangling_def
    table: str
    column: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "table": self.table,
                "column": self.column, "detail": self.detail}


@dataclass
class HygieneReport:
    root: str
    dialect: str
    tables_seen: int = 0
    orphan_outputs: list[HygieneItem] = field(default_factory=list)
    dead_columns: list[HygieneItem] = field(default_factory=list)
    dangling_defs: list[HygieneItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {"orphan_outputs": len(self.orphan_outputs),
                "dead_columns": len(self.dead_columns),
                "dangling_defs": len(self.dangling_defs),
                "total": (len(self.orphan_outputs) + len(self.dead_columns)
                          + len(self.dangling_defs))}

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "dialect": self.dialect,
            "tables_seen": self.tables_seen,
            "counts": self.counts(),
            "orphan_outputs": [i.to_dict() for i in self.orphan_outputs],
            "dead_columns": [i.to_dict() for i in self.dead_columns],
            "dangling_defs": [i.to_dict() for i in self.dangling_defs],
            "warnings": list(self.warnings),
        }


def _analyze(paths: list[Path], dialect: str, root: str) -> HygieneReport:
    graph, load_warnings = from_sql_files(paths, dialect=dialect)
    text = "\n;\n".join(p.read_text(encoding="utf-8") for p in paths)
    ddl_cols, ddl_warnings = collect_columns_from_ddl(text, dialect)

    report = HygieneReport(root=root, dialect=dialect,
                           tables_seen=len(graph.nodes),
                           warnings=[*load_warnings, *ddl_warnings])

    written = set(graph.upstream)          # tables with at least one producer
    read = set(graph.downstream)           # tables with at least one consumer
    ddl_tables = {c.table for c in ddl_cols}

    # orphan outputs: produced, never consumed. Final marts (ads_*) are the
    # warehouse's intended endpoints — exempt them from the orphan verdict.
    for table in sorted(written - read):
        bare = table.rpartition(".")[2]
        if bare.startswith("ads_") or table.split(".")[0] == "ads":
            continue
        report.orphan_outputs.append(HygieneItem(
            kind="orphan_output", table=table,
            detail="written by lineage, never read downstream"))

    # dead columns: the table has readers, this DDL column feeds none of them
    selected_src = set(graph.column_down)
    for col in ddl_cols:
        if col.is_partition or col.table not in read:
            continue
        if (col.table, col.column) not in selected_src:
            report.dead_columns.append(HygieneItem(
                kind="dead_column", table=col.table, column=col.column,
                detail="table is read downstream, column never selected"))

    # dangling definitions: DDL exists, lineage never touches the table
    lineage_tables = written | read
    for table in sorted(ddl_tables - lineage_tables):
        report.dangling_defs.append(HygieneItem(
            kind="dangling_def", table=table,
            detail="defined in DDL, absent from every lineage edge"))

    return report


def analyze_files(paths: list[Path] | list[str], dialect: str = "hive",
                  root: str = "") -> HygieneReport:
    resolved = [Path(p) for p in paths]
    return _analyze(resolved, dialect, root or str(resolved[0]))


def analyze_dir(directory: str | Path, dialect: str = "hive") -> HygieneReport:
    base = Path(directory)
    files = sorted(base.rglob("*.sql"))
    return _analyze(files, dialect, str(base))


def analyze_sql_text(sql_text: str, dialect: str = "hive") -> HygieneReport:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "inline.sql"
        path.write_text(sql_text, encoding="utf-8")
        return _analyze([path], dialect, "<inline>")
