# -*- coding: utf-8 -*-
"""Deterministic DAG health checks over the lineage graph.

Finding kinds (severity):
  cycle           (error)  dependency cycle — unschedulable
  dangling_mid    (warn)   mid-layer table referenced but produced by no job
  unconsumed_mid  (warn)   mid-layer table produced but consumed by nothing
  isolated        (info)   table with no edges at all

Constructive output: Kahn topological batches (what can run in parallel,
in which wave) and the critical path (the longest dependency chain, which
bounds end-to-end latency). Nodes on cycles are excluded from batching and
listed as unschedulable.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from ..data_lineage.graph import LineageGraph

SEVERITIES = ("error", "warn", "info")
_SEV_RANK = {"info": 1, "warn": 2, "error": 3}

# layers that must be produced by some job / consumed by someone
_MID_LAYERS = ("dwd", "dwm", "dws", "dim")
_LAYER_RE = re.compile(r"^(ods|dwd|dwm|dws|dim|ads|tmp|stg)")


def _layer_of(name: str) -> str:
    """Layer from the db name or the table-name prefix: dwd.orders → dwd,
    warehouse.dws_gmv → dws, unknown → ''."""
    db, _, table = name.rpartition(".")
    for part in (db, table):
        m = _LAYER_RE.match(part)
        if m:
            return m.group(1)
    return ""


@dataclass
class DagFinding:
    kind: str
    severity: str
    tables: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "severity": self.severity,
                "tables": list(self.tables)}


@dataclass
class DagReport:
    root: str
    tables: int = 0
    edges: int = 0
    findings: list[DagFinding] = field(default_factory=list)
    batches: list[list[str]] = field(default_factory=list)
    unschedulable: list[str] = field(default_factory=list)
    critical_path: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {level: 0 for level in SEVERITIES}
        for f in self.findings:
            out[f.severity] += 1
        out["total"] = len(self.findings)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "tables": self.tables,
            "edges": self.edges,
            "counts": self.counts(),
            "findings": [f.to_dict() for f in self.findings],
            "batches": [list(b) for b in self.batches],
            "unschedulable": list(self.unschedulable),
            "critical_path": list(self.critical_path),
            "warnings": list(self.warnings),
        }


def _topological_batches(graph: LineageGraph,
                         ) -> tuple[list[list[str]], list[str]]:
    """Kahn layering → (waves, leftover-on-cycles)."""
    indegree = {name: len(graph.upstream.get(name, ()))
                for name in graph.nodes}
    ready = sorted(n for n, d in indegree.items() if d == 0)
    batches: list[list[str]] = []
    seen = 0
    while ready:
        batches.append(ready)
        seen += len(ready)
        nxt: list[str] = []
        for name in ready:
            for down in graph.downstream.get(name, ()):
                indegree[down] -= 1
                if indegree[down] == 0:
                    nxt.append(down)
        ready = sorted(nxt)
    leftover = sorted(n for n in graph.nodes
                      if indegree[n] > 0) if seen < len(graph.nodes) else []
    return batches, leftover


def _critical_path(graph: LineageGraph,
                   batches: list[list[str]]) -> list[str]:
    """Longest path over the acyclic portion, via the batch (topo) order."""
    best_len: dict[str, int] = {}
    best_prev: dict[str, str | None] = {}
    order = [n for batch in batches for n in batch]
    for name in order:
        best_len.setdefault(name, 1)
        best_prev.setdefault(name, None)
        for down in sorted(graph.downstream.get(name, ())):
            if down not in graph.nodes:
                continue
            cand = best_len[name] + 1
            if cand > best_len.get(down, 0):
                best_len[down] = cand
                best_prev[down] = name
    if not best_len:
        return []
    end = max(best_len, key=lambda n: (best_len[n], n))
    path: deque[str] = deque()
    cur: str | None = end
    while cur is not None:
        path.appendleft(cur)
        cur = best_prev.get(cur)
    return list(path)


def check_graph(graph: LineageGraph, root: str = "",
                warnings: list[str] | None = None) -> DagReport:
    report = DagReport(root=root, warnings=list(warnings or []))
    report.tables = len(graph.nodes)
    report.edges = sum(len(v) for v in graph.downstream.values())

    for cycle in graph.find_cycles():
        report.findings.append(DagFinding(
            kind="cycle", severity="error", tables=list(cycle)))

    isolated = set(graph.isolated_tables())
    if isolated:
        report.findings.append(DagFinding(
            kind="isolated", severity="info", tables=sorted(isolated)))

    dangling = sorted(
        name for name in graph.nodes
        if name not in isolated
        and not graph.upstream.get(name)
        and _layer_of(name) in _MID_LAYERS)
    if dangling:
        report.findings.append(DagFinding(
            kind="dangling_mid", severity="warn", tables=dangling))

    unconsumed = sorted(
        name for name in graph.nodes
        if name not in isolated
        and not graph.downstream.get(name)
        and _layer_of(name) in _MID_LAYERS)
    if unconsumed:
        report.findings.append(DagFinding(
            kind="unconsumed_mid", severity="warn", tables=unconsumed))

    report.batches, report.unschedulable = _topological_batches(graph)
    report.critical_path = _critical_path(graph, report.batches)
    report.findings.sort(key=lambda f: (-_SEV_RANK[f.severity], f.kind))
    return report


def check_sql_dir(directory: str, dialect: str = "hive",
                  seatunnel_dir: str | None = None) -> DagReport:
    from ..data_lineage.loaders import from_sql_dir

    graph, warnings = from_sql_dir(directory, dialect=dialect)
    if seatunnel_dir:
        from ..data_lineage.seatunnel_loader import from_seatunnel_dir

        st_graph, st_warnings = from_seatunnel_dir(seatunnel_dir)
        graph.merge(st_graph)
        warnings = list(warnings) + list(st_warnings)
    return check_graph(graph, root=str(directory), warnings=warnings)
