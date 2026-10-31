"""Deterministic multi-DAG concurrency conflict detector.

Input: several DAGs (tasks with deps, duration and resource
declarations — slots / memory_gb / writes), each with a start offset,
plus the cluster capacity.  Every DAG is scheduled ASAP by its own
dependencies (each task starts the moment its upstreams finish); the
combined timeline is then swept for:

* **over-capacity windows** — intervals where total slot or memory
  demand exceeds the capacity, with the tasks involved;
* **write-write conflicts** — tasks from different DAGs whose run
  intervals overlap while writing the same table;
* **a stagger suggestion** — delay the DAG with the smallest footprint
  in the worst window just past that window, then re-simulate and
  report the before/after peak, so the suggestion is verified, not
  hoped.

No scheduler connection — declarations in, timeline verdicts out.
"""

from __future__ import annotations

import dataclasses
import json
import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskRun:
    dag: str
    task: str
    start: float
    finish: float
    slots: int
    memory_gb: float
    writes: tuple[str, ...]


@dataclass
class Scenario:
    cap_slots: int
    cap_memory_gb: float
    starts: dict[str, float]                    # dag → start offset
    dag_tasks: dict[str, list[dict[str, Any]]]  # raw task declarations


def parse_scenario(text: str) -> Scenario:
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("empty scenario")
    data = json.loads(stripped)
    if not isinstance(data, dict) or not isinstance(data.get("dags"), list):
        raise ValueError("scenario needs a 'dags' list")
    cap = data.get("capacity") or {}
    scenario = Scenario(
        cap_slots=int(cap.get("slots") or 0),
        cap_memory_gb=float(cap.get("memory_gb") or 0),
        starts={}, dag_tasks={})
    if scenario.cap_slots <= 0:
        raise ValueError("capacity.slots must be > 0")
    for dag in data["dags"]:
        name = str(dag.get("name") or "").strip()
        if not name:
            raise ValueError("every dag needs a 'name'")
        if name in scenario.dag_tasks:
            raise ValueError(f"duplicate dag name: {name}")
        tasks = dag.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            raise ValueError(f"dag {name} needs a 'tasks' list")
        scenario.starts[name] = float(dag.get("start") or 0)
        scenario.dag_tasks[name] = tasks
    return scenario


def _schedule_dag(name: str, tasks: list[dict[str, Any]],
                  offset: float) -> list[TaskRun]:
    """ASAP schedule by dependencies (unlimited slots within the DAG)."""
    by_name: dict[str, dict[str, Any]] = {}
    for t in tasks:
        tname = str(t.get("name") or "").strip()
        if not tname:
            raise ValueError(f"dag {name}: task missing 'name'")
        by_name[tname] = t
    finish: dict[str, float] = {}

    def resolve(tname: str, chain: tuple[str, ...]) -> float:
        if tname in finish:
            return finish[tname]
        if tname in chain:
            raise ValueError(f"dag {name}: dependency cycle at {tname}")
        t = by_name.get(tname)
        if t is None:
            raise ValueError(f"dag {name}: unknown dependency {tname}")
        deps = t.get("deps") or []
        start = max((resolve(str(d), chain + (tname,)) for d in deps),
                    default=0.0)
        finish[tname] = start + float(t.get("duration") or 1)
        return finish[tname]

    runs: list[TaskRun] = []
    for tname, t in by_name.items():
        end = resolve(tname, ())
        dur = float(t.get("duration") or 1)
        runs.append(TaskRun(
            dag=name, task=tname,
            start=offset + end - dur, finish=offset + end,
            slots=int(t.get("slots") or 1),
            memory_gb=float(t.get("memory_gb") or 0),
            writes=tuple(str(w).lower() for w in (t.get("writes") or []))))
    return runs


@dataclass
class Window:
    start: float
    end: float
    peak_slots: int
    peak_memory_gb: float
    tasks: list[tuple[str, str]] = field(default_factory=list)  # (dag, task)

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start, "end": self.end,
                "peak_slots": self.peak_slots,
                "peak_memory_gb": round(self.peak_memory_gb, 1),
                "tasks": [list(t) for t in self.tasks]}


@dataclass
class ConflictReport:
    cap_slots: int
    cap_memory_gb: float
    peak_slots: int = 0
    peak_memory_gb: float = 0.0
    windows: list[Window] = field(default_factory=list)
    write_conflicts: list[dict[str, Any]] = field(default_factory=list)
    suggestion: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"cap_slots": self.cap_slots,
                "cap_memory_gb": self.cap_memory_gb,
                "peak_slots": self.peak_slots,
                "peak_memory_gb": round(self.peak_memory_gb, 1),
                "windows": [w.to_dict() for w in self.windows],
                "write_conflicts": list(self.write_conflicts),
                "suggestion": dict(self.suggestion)}


def _sweep(runs: list[TaskRun], cap_slots: int,
           cap_mem: float) -> tuple[list[Window], int, float]:
    """Event sweep → maximal over-capacity windows + global peaks."""
    # start/finish deltas per time point: one pass instead of rebuilding
    # the active set at every event
    events: dict[float, tuple[list[TaskRun], list[TaskRun]]] = {}
    for r in runs:
        events.setdefault(r.start, ([], []))[0].append(r)
        events.setdefault(r.finish, ([], []))[1].append(r)
    points = sorted(events)
    windows: list[Window] = []
    peak_slots, peak_mem = 0, 0.0
    current: Window | None = None
    active: list[TaskRun] = []
    slots, mem = 0, 0.0
    for i in range(len(points) - 1):
        t0, t1 = points[i], points[i + 1]
        started, finished = events[t0]
        for r in finished:
            active.remove(r)
            slots -= r.slots
            mem -= r.memory_gb
        for r in started:
            active.append(r)
            slots += r.slots
            mem += r.memory_gb
        peak_slots = max(peak_slots, slots)
        peak_mem = max(peak_mem, mem)
        over = slots > cap_slots or (cap_mem and mem > cap_mem)
        if over:
            if current is None:
                current = Window(start=t0, end=t1, peak_slots=slots,
                                 peak_memory_gb=mem)
            else:
                current.end = t1
                current.peak_slots = max(current.peak_slots, slots)
                current.peak_memory_gb = max(current.peak_memory_gb, mem)
            for r in active:
                if (r.dag, r.task) not in current.tasks:
                    current.tasks.append((r.dag, r.task))
        elif current is not None:
            windows.append(current)
            current = None
    if current is not None:
        windows.append(current)
    return windows, peak_slots, peak_mem


def _runs(scenario: Scenario) -> list[TaskRun]:
    """Schedule every DAG of the scenario onto one shared timeline."""
    runs: list[TaskRun] = []
    for name, tasks in scenario.dag_tasks.items():
        runs.extend(_schedule_dag(name, tasks, scenario.starts[name]))
    return runs


def _write_conflicts(runs: list[TaskRun]) -> list[dict[str, Any]]:
    """Cross-DAG overlapping writers of the same table."""
    conflicts: list[dict[str, Any]] = []
    by_table: dict[str, list[TaskRun]] = {}
    for r in runs:
        for table in r.writes:
            by_table.setdefault(table, []).append(r)
    for table, writers in sorted(by_table.items()):
        for i, a in enumerate(writers):
            for b in writers[i + 1:]:
                if (a.dag != b.dag and a.start < b.finish
                        and b.start < a.finish):
                    conflicts.append({
                        "table": table,
                        "a": f"{a.dag}:{a.task}",
                        "b": f"{b.dag}:{b.task}",
                        "overlap": [max(a.start, b.start),
                                    min(a.finish, b.finish)]})
    return conflicts


def simulate(scenario: Scenario) -> ConflictReport:
    runs = _runs(scenario)
    report = ConflictReport(cap_slots=scenario.cap_slots,
                            cap_memory_gb=scenario.cap_memory_gb)
    report.windows, report.peak_slots, report.peak_memory_gb = _sweep(
        runs, scenario.cap_slots, scenario.cap_memory_gb)
    report.write_conflicts = _write_conflicts(runs)

    if report.windows:
        worst = max(report.windows,
                    key=lambda w: (w.peak_slots, w.end - w.start))
        involvement: dict[str, int] = {}
        for dag, _ in worst.tasks:
            involvement[dag] = involvement.get(dag, 0) + 1
        if len(involvement) > 1:
            # smallest footprint first; ties go to the later-starting
            # DAG (delaying it disturbs the least)
            victim = sorted(
                involvement.items(),
                key=lambda kv: (kv[1], -scenario.starts[kv[0]], kv[0])
            )[0][0]
            delay = math.ceil(worst.end - scenario.starts[victim])
            # per-DAG schedules are offset-invariant: shift the victim's
            # computed runs instead of rescheduling the whole scenario
            shifted = [dataclasses.replace(r, start=r.start + delay,
                                           finish=r.finish + delay)
                       if r.dag == victim else r for r in runs]
            after_windows, after_peak, _ = _sweep(
                shifted, scenario.cap_slots, scenario.cap_memory_gb)
            report.suggestion = {
                "dag": victim, "delay": delay,
                "peak_slots_before": report.peak_slots,
                "peak_slots_after": after_peak,
                "windows_after": len(after_windows)}
    return report


def place(scenario: Scenario, dag_name: str) -> dict[str, Any]:
    """Admission check: find the best start offset for one DAG.

    The named DAG is lifted out of the scenario and re-inserted at
    every candidate offset — 0 and each start/finish boundary of the
    other DAGs' runs (between boundaries the overlap pattern cannot
    change, so boundaries are the only offsets worth trying).  Each
    candidate is fully re-simulated; the winner has the fewest
    conflicts (windows + write conflicts), then the lowest slot peak,
    then the earliest offset.
    """
    if dag_name not in scenario.dag_tasks:
        raise ValueError(f"dag not in the scenario: {dag_name!r}")
    others = [r for name, tasks in scenario.dag_tasks.items()
              if name != dag_name
              for r in _schedule_dag(name, tasks, scenario.starts[name])]
    dag_runs = _schedule_dag(dag_name, scenario.dag_tasks[dag_name], 0.0)

    offsets = {0.0, scenario.starts[dag_name]}
    for r in others:
        offsets.update((r.start, r.finish))
    candidates: list[dict[str, Any]] = []
    for off in sorted(offsets):
        shifted = [dataclasses.replace(r, start=r.start + off,
                                       finish=r.finish + off)
                   for r in dag_runs]
        runs = others + shifted
        windows, peak_slots, _ = _sweep(
            runs, scenario.cap_slots, scenario.cap_memory_gb)
        writes = _write_conflicts(runs)
        candidates.append({"offset": off, "windows": len(windows),
                           "write_conflicts": len(writes),
                           "peak_slots": peak_slots})
    best = min(candidates,
               key=lambda c: (c["windows"] + c["write_conflicts"],
                              c["peak_slots"], c["offset"]))
    declared = next(c for c in candidates
                    if c["offset"] == scenario.starts[dag_name])
    return {"dag": dag_name, "best": best, "declared": declared,
            "candidates": candidates}
