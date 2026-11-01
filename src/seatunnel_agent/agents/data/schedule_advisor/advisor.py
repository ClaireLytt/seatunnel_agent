"""Deterministic schedule advice from task durations and dependencies.

Input is one scheduling day's plan — JSON::

    {"day_start": "00:30",
     "sla": {"task": "ads_board_kpi", "deadline": "07:00"},
     "tasks": [{"name": "ods_load", "duration_min": 40, "deps": []},
               {"name": "dwd_orders", "duration_min": 55,
                "deps": ["ods_load"]}]}

The advisor walks the DAG (cycle-safe): earliest start/finish per task
(a task starts when its last dependency finishes, never before
day_start), the critical path into the SLA task, the SLA safety margin,
per-task slack (how far it can slip without moving the SLA task), and
the peak-parallelism window (how many tasks run at once, and when).
Advice follows: a negative or thin margin names the critical chain to
shorten; big-slack tasks are the ones to shift out of the peak window.
All arithmetic is in minutes after midnight.  No scheduler connection.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

__all__ = ["ScheduleResult", "TaskSlot", "advise_schedule", "parse_plan"]

_THIN_MARGIN_MIN = 30.0
_BIG_SLACK_MIN = 60.0

_HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")


def _minutes(hhmm: str, what: str) -> float:
    m = _HHMM.match((hhmm or "").strip())
    if not m:
        raise ValueError(f"{what}: bad time '{hhmm}', expected HH:MM")
    return int(m.group(1)) * 60 + int(m.group(2))


def _hhmm(minutes: float) -> str:
    minutes = int(round(minutes))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@dataclass
class TaskSlot:
    name: str
    duration_min: float
    deps: list[str]
    start_min: float = 0.0
    finish_min: float = 0.0
    slack_min: float | None = None
    critical: bool = False

    def to_dict(self) -> dict:
        return {"name": self.name, "duration_min": self.duration_min,
                "deps": self.deps, "start": _hhmm(self.start_min),
                "finish": _hhmm(self.finish_min),
                "slack_min": self.slack_min, "critical": self.critical}


@dataclass
class ScheduleResult:
    day_start: str
    sla_task: str
    deadline: str
    finish: str
    margin_min: float | None
    critical_path: list[str]
    peak_parallelism: int
    peak_window: str
    movable: list[dict] = field(default_factory=list)
    tasks: list[TaskSlot] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"day_start": self.day_start, "sla_task": self.sla_task,
                "deadline": self.deadline, "finish": self.finish,
                "margin_min": self.margin_min,
                "critical_path": self.critical_path,
                "peak_parallelism": self.peak_parallelism,
                "peak_window": self.peak_window, "movable": self.movable,
                "tasks": [t.to_dict() for t in self.tasks]}


def parse_plan(text: str) -> dict:
    body = (text or "").strip()
    if not body:
        raise ValueError("empty plan / 计划为空")
    try:
        plan = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"plan must be JSON: {exc}") from exc
    if not isinstance(plan, dict) or not plan.get("tasks"):
        raise ValueError("plan needs a 'tasks' list / 计划缺 tasks")
    names = set()
    for i, t in enumerate(plan["tasks"], start=1):
        if not isinstance(t, dict) or not (t.get("name") or "").strip():
            raise ValueError(f"task {i}: needs 'name'")
        if float(t.get("duration_min") or 0) <= 0:
            raise ValueError(f"task {t['name']}: needs duration_min > 0")
        names.add(t["name"])
    for t in plan["tasks"]:
        for d in t.get("deps") or ():
            if d not in names:
                raise ValueError(f"task {t['name']}: unknown dep '{d}'")
    return plan


def advise_schedule(plan: dict) -> ScheduleResult:
    day_start = _minutes(str(plan.get("day_start") or "00:00"),
                         "day_start")
    slots = {t["name"]: TaskSlot(name=t["name"],
                                 duration_min=float(t["duration_min"]),
                                 deps=list(t.get("deps") or ()))
             for t in plan["tasks"]}

    # topological earliest start/finish (cycle-safe)
    resolved: dict[str, float] = {}
    visiting: set[str] = set()

    def finish_of(name: str) -> float:
        if name in resolved:
            return resolved[name]
        if name in visiting:
            raise ValueError(f"dependency cycle through '{name}' / "
                             f"依赖成环")
        visiting.add(name)
        s = slots[name]
        s.start_min = max([day_start]
                          + [finish_of(d) for d in s.deps])
        s.finish_min = s.start_min + s.duration_min
        visiting.discard(name)
        resolved[name] = s.finish_min
        return s.finish_min

    for name in slots:
        finish_of(name)

    # SLA target: declared, or the latest finisher
    sla = plan.get("sla") or {}
    sla_task = str(sla.get("task") or "").strip()
    if sla_task and sla_task not in slots:
        raise ValueError(f"sla.task '{sla_task}' not in tasks")
    if not sla_task:
        sla_task = max(slots.values(), key=lambda s: s.finish_min).name
    deadline_str = str(sla.get("deadline") or "").strip()
    deadline = _minutes(deadline_str, "sla.deadline") if deadline_str \
        else None

    # critical path: walk back from the SLA task along binding deps
    path = [sla_task]
    while True:
        s = slots[path[-1]]
        binding = [d for d in s.deps
                   if slots[d].finish_min == s.start_min]
        if not binding:
            break
        path.append(sorted(binding)[0])
    path.reverse()
    for name in path:
        slots[name].critical = True

    # slack toward the SLA task: latest start keeping it unmoved
    target_finish = slots[sla_task].finish_min
    latest: dict[str, float] = {}

    def latest_start(name: str) -> float:
        if name in latest:
            return latest[name]
        dependents = [s for s in slots.values() if name in s.deps]
        if name == sla_task or not dependents:
            lf = (target_finish if name == sla_task
                  else slots[name].finish_min)
        else:
            lf = min(latest_start(d.name) for d in dependents)
        latest[name] = lf - slots[name].duration_min
        return latest[name]

    feeders = _ancestors(slots, sla_task) | {sla_task}
    for name in feeders:
        slots[name].slack_min = round(
            latest_start(name) - slots[name].start_min, 1)

    # peak parallelism over the whole day
    events = sorted([(s.start_min, 1) for s in slots.values()]
                    + [(s.finish_min, -1) for s in slots.values()])
    running = peak = 0
    peak_at = day_start
    for at, delta in events:
        running += delta
        if running > peak:
            peak, peak_at = running, at
    margin = (deadline - target_finish) if deadline is not None else None

    movable = sorted(
        ({"name": s.name, "slack_min": s.slack_min}
         for s in slots.values()
         if s.slack_min is not None and s.slack_min >= _BIG_SLACK_MIN),
        key=lambda m: -m["slack_min"])
    ordered = sorted(slots.values(), key=lambda s: (s.start_min, s.name))
    return ScheduleResult(
        day_start=_hhmm(day_start), sla_task=sla_task,
        deadline=deadline_str or "-", finish=_hhmm(target_finish),
        margin_min=round(margin, 1) if margin is not None else None,
        critical_path=path, peak_parallelism=peak,
        peak_window=_hhmm(peak_at), movable=movable[:8], tasks=ordered)


def _ancestors(slots: dict[str, TaskSlot], name: str) -> set[str]:
    seen: set[str] = set()
    stack = list(slots[name].deps)
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(slots[n].deps)
    return seen
