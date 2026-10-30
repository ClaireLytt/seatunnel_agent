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

__all__ = ["RerunPlan", "RerunTask", "parse_dag", "parse_statuses",
           "plan_rerun"]

# scheduler-export states mapped onto failed / succeeded
_FAILED_STATES = ("failed", "error", "failure", "up_for_retry", "killed")
_SUCCESS_STATES = ("success", "succeeded", "ok", "done")


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
    batch_etas: list[float] = field(default_factory=list)  # max dur per batch
    total_eta: float = 0.0  # sum of batch ETAs (batches run sequentially)
    # connected components of the rerun set — independent recovery tracks
    groups: list[list[str]] = field(default_factory=list)

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
            "batch_etas": list(self.batch_etas),
            "total_eta": self.total_eta,
            "groups": [list(g) for g in self.groups],
        }


def parse_statuses(text: str) -> tuple[list[str], list[str]]:
    """Scheduler status export → (failed, succeeded).

    JSON object ``{"task": "state"}`` or ``task=state`` / ``task,state``
    lines.  Failed states: failed/error/failure/up_for_retry/killed;
    success states: success/succeeded/ok/done; anything else (running,
    queued, skipped...) is neither.
    """
    import json

    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("empty status export")
    if stripped[0] == "{":
        data = json.loads(stripped)
        if not isinstance(data, dict):
            raise ValueError("status JSON must be an object")
        items = [(str(k), str(v)) for k, v in data.items()]
    else:
        items = []
        for raw in stripped.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            sep = "=" if "=" in line else ","
            name, _, state = line.partition(sep)
            if not name.strip() or not state.strip():
                raise ValueError(f"status line must be 'task=state': {line!r}")
            items.append((name.strip(), state.strip()))
    failed = [n for n, s in items if s.lower() in _FAILED_STATES]
    succeeded = [n for n, s in items if s.lower() in _SUCCESS_STATES]
    if not failed:
        raise ValueError("status export contains no failed tasks")
    return failed, succeeded


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
    # ETA: tasks within a batch run in parallel (max), batches in sequence
    plan.batch_etas = [round(max(graph.nodes[n] for n in batch), 2)
                       for batch in batches]
    plan.total_eta = round(sum(plan.batch_etas), 2)
    plan.groups = _recovery_groups(graph, members)
    return plan


def _recovery_groups(graph: TaskGraph,
                     members: set[str]) -> list[list[str]]:
    """Connected components of the rerun subgraph (edges both ways) —
    each group recovers independently of the others."""
    seen: set[str] = set()
    groups: list[list[str]] = []
    for start in sorted(members):
        if start in seen:
            continue
        component: list[str] = []
        stack = [start]
        seen.add(start)
        while stack:
            node = stack.pop()
            component.append(node)
            for nxt in (graph.up[node] | graph.down[node]) & members:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        groups.append(sorted(component))
    return groups
