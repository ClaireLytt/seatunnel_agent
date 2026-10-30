"""Deterministic minimal-impact rerun planner.

Input: a task dependency graph (same formats as the DAG optimizer) plus
the failed task names.  The rerun set is the failed tasks and their
downstream closure — upstream outputs already exist, siblings are
untouched.  Tasks in the closure that had already succeeded are
re-run anyway (their inputs are now stale) and flagged.  The set is
ordered into topological batches over the induced subgraph.

No scheduler or database connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.agents.data.dag_optimize.optimizer import (
    TaskGraph,
    parse_dag,
)

__all__ = ["RerunPlan", "RerunTask", "parse_dag", "plan_rerun"]


@dataclass
class RerunTask:
    task: str
    batch: int
    reason: str            # "failed" | "downstream"
    from_failed: list[str]  # failed roots this task descends from
    stale_success: bool = False  # had succeeded, re-run because inputs changed

    def to_dict(self) -> dict[str, Any]:
        return {"task": self.task, "batch": self.batch,
                "reason": self.reason,
                "from_failed": list(self.from_failed),
                "stale_success": self.stale_success}


@dataclass
class RerunPlan:
    tasks: list[RerunTask] = field(default_factory=list)
    total: int = 0          # tasks in the DAG
    batches: int = 0
    untouched: list[str] = field(default_factory=list)
    unschedulable: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def blast_radius(self) -> float:
        return round(len(self.tasks) / self.total, 3) if self.total else 0.0

    def commands(self, template: str) -> list[str]:
        return [template.format(task=t.task) for t in self.tasks]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tasks": [t.to_dict() for t in self.tasks],
            "total": self.total,
            "batches": self.batches,
            "blast_radius": self.blast_radius,
            "untouched": list(self.untouched),
            "unschedulable": list(self.unschedulable),
            "warnings": list(self.warnings),
        }


def _parse_names(raw: str) -> list[str]:
    seen: list[str] = []
    for part in raw.replace("\n", ",").split(","):
        name = part.strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def _downstream_closure(graph: TaskGraph,
                        roots: list[str]) -> dict[str, set[str]]:
    """task → the failed roots it descends from (roots map to themselves)."""
    origin: dict[str, set[str]] = {r: {r} for r in roots}
    stack = list(roots)
    while stack:
        node = stack.pop()
        for down in sorted(graph.down[node]):
            before = len(origin.get(down, ()))
            origin.setdefault(down, set()).update(origin[node] - {down})
            if len(origin[down]) > before:
                stack.append(down)
    return origin


def _subgraph_batches(graph: TaskGraph,
                      members: set[str]) -> tuple[list[list[str]], list[str]]:
    indegree = {n: len(graph.up[n] & members) for n in members}
    ready = sorted(n for n, d in indegree.items() if d == 0)
    batches: list[list[str]] = []
    seen = 0
    while ready:
        batches.append(ready)
        seen += len(ready)
        nxt: list[str] = []
        for name in ready:
            for down in graph.down[name]:
                if down not in members:
                    continue
                indegree[down] -= 1
                if indegree[down] == 0:
                    nxt.append(down)
        ready = sorted(nxt)
    leftover = sorted(n for n, d in indegree.items() if d > 0) \
        if seen < len(members) else []
    return batches, leftover


def plan_rerun(graph: TaskGraph, failed: str | list[str],
               succeeded: str | list[str] = "") -> RerunPlan:
    failed_names = (_parse_names(failed) if isinstance(failed, str)
                    else list(failed))
    ok_names = (_parse_names(succeeded) if isinstance(succeeded, str)
                else list(succeeded))
    if not failed_names:
        raise ValueError("no failed tasks given")
    unknown = sorted(set(failed_names + ok_names) - set(graph.nodes))
    if unknown:
        raise ValueError(f"unknown task(s): {', '.join(unknown)}")
    overlap = sorted(set(failed_names) & set(ok_names))
    if overlap:
        raise ValueError(
            f"task(s) both failed and succeeded: {', '.join(overlap)}")

    origin = _downstream_closure(graph, failed_names)
    members = set(origin)
    batches, leftover = _subgraph_batches(graph, members)
    plan = RerunPlan(total=len(graph.nodes), batches=len(batches),
                     unschedulable=leftover)
    if leftover:
        plan.warnings.append(
            "cycle: " + ", ".join(leftover) + " cannot be ordered")
    for i, batch in enumerate(batches, 1):
        for name in batch:
            roots = sorted(origin[name] - {name})
            plan.tasks.append(RerunTask(
                task=name, batch=i,
                reason="failed" if name in failed_names else "downstream",
                from_failed=roots,
                stale_success=name in ok_names and name not in failed_names))
    plan.untouched = sorted(set(graph.nodes) - members)
    return plan
