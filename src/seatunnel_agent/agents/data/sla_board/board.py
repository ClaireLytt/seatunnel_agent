"""Deterministic SLA attainment board over task completion records.

schedule_advisor plans when jobs should run and task_failure explains
why they crash; this agent measures the promise everyone actually signs:
did the task finish by its deadline?  Paste the completion records
(sample_profile's parser reused) — columns ``task``, ``date``,
``deadline``, ``finish`` — and per task the board reports the
attainment rate, the lateness distribution (p50/p90/worst), and the
miss streaks, graded:

* SL001 — attainment below target (medium under {target}%, high
  under 80%);
* SL002 high — the task is in a live miss streak of 3+ days;
* SL003 medium — p90 lateness over 60 minutes: chronically, not
  marginally, late.

Times accept ``HH:MM`` (scheduler convention: hours may pass 24 for
past-midnight finishes, e.g. ``25:30``) or full ISO datetimes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["SlaBoard", "SlaFinding", "TaskSla", "build_board"]

_HM_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_RATE_HIGH = 0.80
_STREAK_MIN = 3
_P90_LATE_MIN = 60.0


def _to_minutes(value: str, what: str) -> float:
    """'HH:MM' (hours may exceed 24) or ISO datetime → minutes."""
    v = (value or "").strip()
    m = _HM_RE.match(v)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(v)
        return dt.timestamp() / 60
    except ValueError:
        raise ValueError(f"{what}: cannot parse time '{v}' "
                         "(use HH:MM or an ISO datetime)")


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, round(q * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


@dataclass
class TaskSla:
    task: str
    runs: int = 0
    misses: int = 0
    rate: float = 1.0
    p50_late_min: float = 0.0     # over the late runs only
    p90_late_min: float = 0.0
    worst_late_min: float = 0.0
    max_streak: int = 0           # longest consecutive-miss run
    live_streak: int = 0          # misses ending at the latest record

    def to_dict(self) -> dict[str, Any]:
        return {"task": self.task, "runs": self.runs,
                "misses": self.misses, "rate": round(self.rate, 4),
                "p50_late_min": round(self.p50_late_min, 1),
                "p90_late_min": round(self.p90_late_min, 1),
                "worst_late_min": round(self.worst_late_min, 1),
                "max_streak": self.max_streak,
                "live_streak": self.live_streak}


@dataclass
class SlaFinding:
    code: str            # SL001..SL003
    severity: str        # high | medium
    task: str
    value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "task": self.task, "value": round(self.value, 4)}


@dataclass
class SlaBoard:
    target: float
    tasks: list[TaskSla] = field(default_factory=list)
    findings: list[SlaFinding] = field(default_factory=list)
    runs_total: int = 0
    misses_total: int = 0

    @property
    def overall_rate(self) -> float:
        return (1 - self.misses_total / self.runs_total
                if self.runs_total else 1.0)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"target": self.target,
                "runs_total": self.runs_total,
                "misses_total": self.misses_total,
                "overall_rate": round(self.overall_rate, 4),
                "counts": self.counts(),
                "tasks": [t.to_dict() for t in self.tasks],
                "findings": [f.to_dict() for f in self.findings]}


def build_board(headers: list[str], rows: list[dict[str, str | None]],
                target: float = 0.95) -> SlaBoard:
    """Completion records → per-task SLA board, worst first."""
    needed = {"task", "date", "deadline", "finish"}
    missing = needed - {h.lower() for h in headers}
    if missing:
        raise ValueError("records need columns task/date/deadline/finish "
                         f"— missing: {', '.join(sorted(missing))}")
    if not rows:
        raise ValueError("no completion records to score")
    if not 0.5 <= target <= 1.0:
        raise ValueError("target must be within [0.5, 1.0]")
    col = {h.lower(): h for h in headers}

    per_task: dict[str, list[tuple[str, float]]] = {}   # (date, late_min)
    for i, r in enumerate(rows):
        task = str(r.get(col["task"]) or "").strip()
        date = str(r.get(col["date"]) or "").strip()
        if not task or not date:
            raise ValueError(f"row {i + 1}: task and date are required")
        deadline = _to_minutes(str(r.get(col["deadline"]) or ""),
                               f"row {i + 1} deadline")
        finish = _to_minutes(str(r.get(col["finish"]) or ""),
                             f"row {i + 1} finish")
        per_task.setdefault(task, []).append((date, finish - deadline))

    board = SlaBoard(target=target)
    for task in sorted(per_task):
        records = sorted(per_task[task])          # chronological by date
        lates = [late for _, late in records]
        misses = [late for late in lates if late > 0]
        t = TaskSla(task=task, runs=len(lates), misses=len(misses))
        t.rate = 1 - t.misses / t.runs
        late_sorted = sorted(misses)
        t.p50_late_min = _percentile(late_sorted, 0.5)
        t.p90_late_min = _percentile(late_sorted, 0.9)
        t.worst_late_min = late_sorted[-1] if late_sorted else 0.0
        streak = 0
        for _, late in records:
            streak = streak + 1 if late > 0 else 0
            t.max_streak = max(t.max_streak, streak)
        t.live_streak = streak
        board.tasks.append(t)
        board.runs_total += t.runs
        board.misses_total += t.misses

        if t.rate < target:
            board.findings.append(SlaFinding(
                code="SL001",
                severity="high" if t.rate < _RATE_HIGH else "medium",
                task=task, value=t.rate))
        if t.live_streak >= _STREAK_MIN:
            board.findings.append(SlaFinding(
                code="SL002", severity="high", task=task,
                value=t.live_streak))
        if t.p90_late_min > _P90_LATE_MIN:
            board.findings.append(SlaFinding(
                code="SL003", severity="medium", task=task,
                value=t.p90_late_min))

    board.tasks.sort(key=lambda t: (t.rate, -t.live_streak))
    order = {"high": 0, "medium": 1, "low": 2}
    board.findings.sort(key=lambda f: (order[f.severity], f.code, f.task))
    return board
