"""Deterministic task-DAG dependency optimizer.

Input: a task dependency graph (JSON ``tasks``/``edges`` or ``a -> b``
text lines), optional per-task durations.  Output:

* redundant edges — direct dependencies already implied by a longer
  path (transitive reduction), each with the witness path;
* parallel waves — Kahn layering, width per wave, max parallelism;
* critical path — longest chain by duration (default 1 per task),
  with the ideal speedup (total duration / critical-path duration);
* serial chains — single-in/single-out runs that could be fused;
* cycles — nodes excluded from scheduling, listed separately.

No scheduler or database connection.
"""

from __future__ import annotations

import heapq
import json
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

WORKER_COUNTS = (1, 2, 4, 8)

_ARROW_RE = re.compile(r"\s*->\s*|\s*=>\s*")
_DOT_HEAD_RE = re.compile(r"^\s*(strict\s+)?(di)?graph\b", re.IGNORECASE)
_DOT_ATTR_RE = re.compile(r"\[[^\]]*\]")  # [label=..., shape=...]


@dataclass
class TaskGraph:
    """Parsed task DAG: adjacency both ways + per-task durations."""

    nodes: dict[str, float] = field(default_factory=dict)  # name → duration
    up: dict[str, set[str]] = field(default_factory=dict)
    down: dict[str, set[str]] = field(default_factory=dict)

    def add_node(self, name: str, duration: float | None = None) -> None:
        name = name.strip()
        if not name:
            return
        if name not in self.nodes or duration is not None:
            self.nodes[name] = float(duration) if duration is not None \
                else self.nodes.get(name, 1.0)
        self.up.setdefault(name, set())
        self.down.setdefault(name, set())

    def add_edge(self, upstream: str, downstream: str) -> None:
        upstream, downstream = upstream.strip(), downstream.strip()
        if not upstream or not downstream or upstream == downstream:
            return
        self.add_node(upstream)
        self.add_node(downstream)
        self.down[upstream].add(downstream)
        self.up[downstream].add(upstream)

    @property
    def edges(self) -> list[tuple[str, str]]:
        return sorted((u, d) for u, downs in self.down.items()
                      for d in downs)


def _from_task_list(items: list[Any], graph: TaskGraph) -> None:
    for item in items:
        if isinstance(item, str):
            graph.add_node(item)
            continue
        if not isinstance(item, dict):
            raise ValueError(f"task entry must be object or string: {item!r}")
        name = str(item.get("name") or item.get("task") or "").strip()
        if not name:
            raise ValueError(f"task entry missing 'name': {item!r}")
        duration = item.get("duration")
        if duration is not None:
            duration = float(duration)
            if duration <= 0:
                raise ValueError(f"duration must be > 0: {name}")
        graph.add_node(name, duration)
        deps = item.get("deps") or item.get("depends_on") or []
        if isinstance(deps, str):
            deps = [deps]
        for dep in deps:
            graph.add_edge(str(dep), name)


def _from_edge_list(items: list[Any], graph: TaskGraph) -> None:
    for item in items:
        if isinstance(item, dict):
            u = str(item.get("up") or item.get("from") or
                    item.get("upstream") or "")
            d = str(item.get("down") or item.get("to") or
                    item.get("downstream") or "")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            u, d = str(item[0]), str(item[1])
        else:
            raise ValueError(f"edge must be [up, down] or object: {item!r}")
        if not u or not d:
            raise ValueError(f"edge missing endpoint: {item!r}")
        graph.add_edge(u, d)


def _strip_dot(text: str) -> str:
    """Graphviz DOT (``airflow dags show`` output) → plain edge lines.

    Drops the digraph header, braces, per-line attribute blocks,
    ``graph/node/edge`` defaults and ``key=value`` statements; unquotes
    names and strips trailing semicolons. What remains is the ``a -> b``
    syntax the plain-text parser already understands.
    """
    out: list[str] = []
    for raw in text.splitlines():
        line = _DOT_ATTR_RE.sub("", raw).strip()
        line = line.strip("{}").strip().rstrip(";").strip()
        if (not line or _DOT_HEAD_RE.match(line)
                or line.split("=")[0].strip().lower() in
                ("rankdir", "label", "labelloc", "bgcolor", "splines")
                or line.lower() in ("graph", "node", "edge")):
            continue
        out.append(line.replace('"', ""))
    return "\n".join(out)


def _from_text_lines(text: str, graph: TaskGraph) -> None:
    if _DOT_HEAD_RE.match(text.lstrip()):
        text = _strip_dot(text)
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "->" in line or "=>" in line:
            parts = [p for p in _ARROW_RE.split(line) if p.strip()]
            for u, d in zip(parts, parts[1:]):
                graph.add_edge(u, d)
        elif "," in line:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 2 or not all(parts):
                raise ValueError(f"CSV line must be 'up,down': {line!r}")
            if parts == ["up", "down"] or parts == ["task", "dep"]:
                continue  # header
            graph.add_edge(parts[0], parts[1])
        else:
            graph.add_node(line)


def parse_dag(text: str) -> TaskGraph:
    """JSON (``tasks``/``edges``/task list) or text lines → TaskGraph."""
    graph = TaskGraph()
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("empty DAG input")
    if stripped[0] in "[{":
        data = json.loads(stripped)
        if isinstance(data, dict):
            tasks = data.get("tasks")
            edges = data.get("edges")
            if tasks is None and edges is None:
                raise ValueError("JSON object needs 'tasks' or 'edges'")
            if tasks:
                _from_task_list(tasks, graph)
            if edges:
                _from_edge_list(edges, graph)
        elif isinstance(data, list):
            if data and isinstance(data[0], (list, tuple)):
                _from_edge_list(data, graph)
            else:
                _from_task_list(data, graph)
        else:
            raise ValueError("JSON must be an object or a list")
    else:
        _from_text_lines(stripped, graph)
    if not graph.nodes:
        raise ValueError("no tasks found in input")
    return graph


# ----------------------------------------------------------------------
# analysis
# ----------------------------------------------------------------------

@dataclass
class RedundantEdge:
    up: str
    down: str
    via: list[str]  # witness path up → ... → down (without the direct edge)

    def to_dict(self) -> dict[str, Any]:
        return {"up": self.up, "down": self.down, "via": list(self.via)}


@dataclass
class DagOptimizeResult:
    tasks: int = 0
    edges: int = 0
    redundant: list[RedundantEdge] = field(default_factory=list)
    batches: list[list[str]] = field(default_factory=list)
    max_width: int = 0
    critical_path: list[str] = field(default_factory=list)
    critical_duration: float = 0.0
    total_duration: float = 0.0
    speedup: float = 1.0
    chains: list[list[str]] = field(default_factory=list)
    cycles: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    makespans: dict[str, float] = field(default_factory=dict)  # workers → time
    # critical tasks, most impactful first: task, duration, and the
    # critical-path duration if that one task were cut in half
    bottlenecks: list[dict[str, Any]] = field(default_factory=list)
    # the task JSON with redundant edges removed — pasteable back
    optimized: dict[str, Any] = field(default_factory=dict)
    deadline: float = 0.0          # SLA duration the caller asked about
    deadline_met: bool | None = None
    # critical tasks to halve (in gain order) until the deadline holds
    deadline_plan: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tasks": self.tasks,
            "edges": self.edges,
            "redundant": [r.to_dict() for r in self.redundant],
            "batches": [list(b) for b in self.batches],
            "max_width": self.max_width,
            "critical_path": list(self.critical_path),
            "critical_duration": self.critical_duration,
            "total_duration": self.total_duration,
            "speedup": self.speedup,
            "chains": [list(c) for c in self.chains],
            "cycles": list(self.cycles),
            "warnings": list(self.warnings),
            "makespans": dict(self.makespans),
            "bottlenecks": [dict(b) for b in self.bottlenecks],
            "optimized": dict(self.optimized),
            "deadline": self.deadline,
            "deadline_met": self.deadline_met,
            "deadline_plan": list(self.deadline_plan),
        }


def _kahn_batches(graph: TaskGraph,
                  skip: set[str]) -> tuple[list[list[str]], list[str]]:
    indegree = {n: len([u for u in graph.up[n] if u not in skip])
                for n in graph.nodes if n not in skip}
    ready = sorted(n for n, d in indegree.items() if d == 0)
    batches: list[list[str]] = []
    seen = 0
    while ready:
        batches.append(ready)
        seen += len(ready)
        nxt: list[str] = []
        for name in ready:
            for down in graph.down[name]:
                if down in skip:
                    continue
                indegree[down] -= 1
                if indegree[down] == 0:
                    nxt.append(down)
        ready = sorted(nxt)
    leftover = sorted(n for n, d in indegree.items() if d > 0) \
        if seen < len(indegree) else []
    return batches, leftover


def _witness_path(graph: TaskGraph, up: str, down: str,
                  skip: set[str]) -> list[str] | None:
    """Shortest alternate path up → down avoiding the direct edge."""
    prev: dict[str, str] = {}
    queue = deque(sorted(graph.down[up] - {down} - skip))
    for n in queue:
        prev[n] = up
    while queue:
        node = queue.popleft()
        if node == down:
            path = [node]
            while path[-1] != up:
                path.append(prev[path[-1]])
            return list(reversed(path))
        for nxt in sorted(graph.down[node]):
            if nxt in prev or nxt in skip or nxt == up:
                continue
            prev[nxt] = node
            queue.append(nxt)
    return None


def _critical_path(graph: TaskGraph,
                   order: list[str]) -> tuple[list[str], float]:
    best: dict[str, float] = {}
    prev: dict[str, str | None] = {}
    for name in order:
        best.setdefault(name, graph.nodes[name])
        prev.setdefault(name, None)
        for down in sorted(graph.down[name]):
            if down not in graph.nodes:
                continue
            cand = best[name] + graph.nodes[down]
            if cand > best.get(down, 0.0):
                best[down] = cand
                prev[down] = name
    if not best:
        return [], 0.0
    # deterministic argmax without sorting every node: longest duration,
    # ties broken by name
    end = min(best, key=lambda n: (-best[n], n))
    path = [end]
    node = prev.get(end)
    while node:
        path.append(node)
        node = prev.get(node)
    return list(reversed(path)), best[end]


def _serial_chains(graph: TaskGraph, skip: set[str]) -> list[list[str]]:
    """Maximal runs a→b→c where every link is single-out → single-in."""
    def linked(u: str, d: str) -> bool:
        return (u not in skip and d not in skip
                and graph.down[u] == {d} and graph.up[d] == {u})

    chains: list[list[str]] = []
    for name in sorted(graph.nodes):
        if name in skip:
            continue
        # chain starts where the node is not itself a chain interior
        ups = graph.up[name]
        if len(ups) == 1 and linked(next(iter(ups)), name):
            continue
        chain = [name]
        while True:
            downs = graph.down[chain[-1]]
            if len(downs) == 1 and linked(chain[-1], next(iter(downs))):
                chain.append(next(iter(downs)))
            else:
                break
        if len(chain) >= 3:
            chains.append(chain)
    return chains


def makespan(graph: TaskGraph, order: list[str], workers: int) -> float:
    """List scheduling: topo order, earliest-free worker, dep-gated starts."""
    finish: dict[str, float] = {}
    free = [0.0] * workers
    heapq.heapify(free)
    for name in order:
        earliest = max((finish[u] for u in graph.up[name]
                        if u in finish), default=0.0)
        start = max(heapq.heappop(free), earliest)
        finish[name] = start + graph.nodes[name]
        heapq.heappush(free, finish[name])
    return max(finish.values(), default=0.0)


def _deadline_plan(graph: TaskGraph, order: list[str],
                   bottlenecks: list[dict[str, Any]],
                   deadline: float) -> tuple[bool, list[str]]:
    """Halve bottleneck tasks (best gain first, cumulatively) until the
    critical path fits the deadline. Returns (met, tasks halved)."""
    halved: list[str] = []
    saved: dict[str, float] = {}
    try:
        for b in bottlenecks:
            _, duration = _critical_path(graph, order)
            if duration <= deadline:
                return True, halved
            name = b["task"]
            saved[name] = graph.nodes[name]
            graph.nodes[name] = saved[name] / 2
            halved.append(name)
        _, duration = _critical_path(graph, order)
        return duration <= deadline, halved
    finally:
        graph.nodes.update(saved)


@dataclass
class DagDiff:
    """Change review between a baseline DAG and the new one."""

    added_tasks: list[str] = field(default_factory=list)
    removed_tasks: list[str] = field(default_factory=list)
    added_edges: list[tuple[str, str]] = field(default_factory=list)
    removed_edges: list[tuple[str, str]] = field(default_factory=list)
    critical_before: float = 0.0
    critical_after: float = 0.0
    makespan2_before: float = 0.0   # 2-worker list-scheduling makespan
    makespan2_after: float = 0.0
    new_redundant: list[RedundantEdge] = field(default_factory=list)

    @property
    def critical_delta(self) -> float:
        return round(self.critical_after - self.critical_before, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "added_tasks": list(self.added_tasks),
            "removed_tasks": list(self.removed_tasks),
            "added_edges": [list(e) for e in self.added_edges],
            "removed_edges": [list(e) for e in self.removed_edges],
            "critical_before": self.critical_before,
            "critical_after": self.critical_after,
            "critical_delta": self.critical_delta,
            "makespan2_before": self.makespan2_before,
            "makespan2_after": self.makespan2_after,
            "new_redundant": [r.to_dict() for r in self.new_redundant],
        }


def diff_dags(base: TaskGraph, new: TaskGraph,
              after: DagOptimizeResult | None = None) -> DagDiff:
    """Structural and latency deltas introduced by the change.

    Callers that already ran ``optimize(new)`` pass the result as
    ``after`` so the full analysis is not recomputed."""
    base_edges, new_edges = set(base.edges), set(new.edges)
    before = optimize(base)
    if after is None:
        after = optimize(new)
    base_redundant = {(r.up, r.down) for r in before.redundant}
    return DagDiff(
        added_tasks=sorted(set(new.nodes) - set(base.nodes)),
        removed_tasks=sorted(set(base.nodes) - set(new.nodes)),
        added_edges=sorted(new_edges - base_edges),
        removed_edges=sorted(base_edges - new_edges),
        critical_before=round(before.critical_duration, 2),
        critical_after=round(after.critical_duration, 2),
        makespan2_before=before.makespans.get("2", 0.0),
        makespan2_after=after.makespans.get("2", 0.0),
        new_redundant=[r for r in after.redundant
                       if (r.up, r.down) not in base_redundant],
    )


def optimize(graph: TaskGraph, deadline: float = 0.0) -> DagOptimizeResult:
    edges = graph.edges  # the property builds+sorts; bind once
    result = DagOptimizeResult(tasks=len(graph.nodes), edges=len(edges))
    batches, on_cycle = _kahn_batches(graph, skip=set())
    result.cycles = on_cycle
    skip = set(on_cycle)
    if skip:
        batches, _ = _kahn_batches(graph, skip=skip)
        result.warnings.append(
            f"cycle: {len(skip)} task(s) excluded from analysis")
    result.batches = batches
    result.max_width = max((len(b) for b in batches), default=0)
    order = [n for b in batches for n in b]
    # redundancy via per-node descendant sets (one pass in reverse topo
    # order) — the per-edge BFS only runs for edges already known
    # redundant, to produce the witness path
    descendants: dict[str, set[str]] = {}
    for name in reversed(order):
        desc: set[str] = set()
        for child in graph.down[name]:
            if child in skip:
                continue
            desc.add(child)
            desc |= descendants.get(child, set())
        descendants[name] = desc
    for up, down in edges:
        if up in skip or down in skip:
            continue
        if any(down in descendants.get(child, ())
               for child in graph.down[up] if child != down):
            via = _witness_path(graph, up, down, skip)
            if via:
                result.redundant.append(RedundantEdge(up, down, via))
    result.critical_path, result.critical_duration = _critical_path(
        graph, order)
    result.total_duration = sum(graph.nodes[n] for n in order)
    if result.critical_duration > 0:
        result.speedup = round(
            result.total_duration / result.critical_duration, 2)
    result.chains = _serial_chains(graph, skip)
    for k in WORKER_COUNTS:
        result.makespans[str(k)] = round(makespan(graph, order, k), 2)
    result.makespans["inf"] = round(result.critical_duration, 2)
    result.bottlenecks = _bottlenecks(graph, order, result.critical_path,
                                      result.critical_duration)
    if deadline > 0:
        result.deadline = deadline
        if result.critical_duration <= deadline:
            result.deadline_met = True
        else:
            met, plan = _deadline_plan(graph, order, result.bottlenecks,
                                       deadline)
            result.deadline_met = met
            result.deadline_plan = plan
    if result.redundant:
        drop = {(r.up, r.down) for r in result.redundant}
        result.optimized = {"tasks": [
            {"name": name,
             "deps": sorted(u for u in graph.up[name]
                            if (u, name) not in drop),
             "duration": graph.nodes[name]}
            for name in sorted(graph.nodes)]}
    return result


def _bottlenecks(graph: TaskGraph, order: list[str],
                 critical_path: list[str], critical_duration: float,
                 top: int = 3) -> list[dict[str, Any]]:
    """What-if per critical task: halve it, recompute the critical path.

    The tasks whose speedup shrinks end-to-end latency the most come
    first — they are where optimisation effort pays.
    """
    out: list[dict[str, Any]] = []
    for name in critical_path:
        saved = graph.nodes[name]
        graph.nodes[name] = saved / 2
        _, new_duration = _critical_path(graph, order)
        graph.nodes[name] = saved
        out.append({"task": name, "duration": saved,
                    "halved_critical": round(new_duration, 2),
                    "gain": round(critical_duration - new_duration, 2)})
    out.sort(key=lambda b: (-b["gain"], b["task"]))
    return out[:top]
