"""Critical-path and delay attribution over one scheduling run.

Input model: a list of task instances — ``name``, ``start``, ``end``
(ISO timestamps), ``deps`` (upstream task names). JSON is a list of such
objects (synonyms accepted: task/task_id for name, start_time/start_date,
end_time/end_date, depends_on/upstream for deps, comma-separated string ok);
CSV uses the same column names.

Analysis for a target task (default: the one ending last):

* **critical path** — walking upstream from the target, always into the
  dependency that finished last (the one the task actually waited for),
* per task on the path: **run** (end-start) and **wait** (start minus the
  latest dependency end; for roots, start minus the run's first start),
* **SLA check** — the target's end vs an optional deadline,
* top delay contributors on the path, so "who made it late" is one list.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

MAX_INSTANCES = 50_000

_NAME_KEYS = ("name", "task", "task_id", "task_name")
_START_KEYS = ("start", "start_time", "start_date")
_END_KEYS = ("end", "end_time", "end_date")
_DEPS_KEYS = ("deps", "depends_on", "upstream", "upstream_tasks")


@dataclass
class TaskInstance:
    name: str
    start: datetime
    end: datetime
    deps: tuple[str, ...] = ()

    @property
    def run_s(self) -> float:
        return (self.end - self.start).total_seconds()


@dataclass
class PathStep:
    task: TaskInstance
    wait_s: float           # waited on deps (or on the run start, for roots)
    blocking: str = ""      # the dependency this task actually waited for

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.task.name,
            "start": self.task.start.isoformat(sep=" "),
            "end": self.task.end.isoformat(sep=" "),
            "run_s": round(self.task.run_s, 1),
            "wait_s": round(self.wait_s, 1),
            "blocking": self.blocking,
        }


@dataclass
class SlaTrace:
    target: str
    instances: int
    path: list[PathStep] = field(default_factory=list)  # upstream → target
    deadline: datetime | None = None
    finished_at: datetime | None = None
    breach_s: float = 0.0       # >0: finished this many seconds late
    warnings: list[str] = field(default_factory=list)

    @property
    def total_s(self) -> float:
        if not self.path:
            return 0.0
        return (self.path[-1].task.end - self.path[0].task.start
                ).total_seconds()

    def top_delays(self, n: int = 5) -> list[tuple[PathStep, float]]:
        """Path steps by their contribution (run + wait), largest first."""
        scored = [(s, s.task.run_s + s.wait_s) for s in self.path]
        scored.sort(key=lambda t: -t[1])
        return scored[:n]


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def _parse_ts(value: Any, what: str) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", ""))
    except ValueError as exc:
        raise ValueError(f"无法解析时间 {what}={value!r}: {exc}") from exc


def _parse_deps(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(";", ",").split(",")]
        return tuple(p for p in parts if p)
    return tuple(str(v).strip() for v in value if str(v).strip())


def _row_to_instance(row: dict[str, Any], idx: int) -> TaskInstance:
    name = _pick(row, _NAME_KEYS)
    if not name:
        raise ValueError(f"第 {idx} 条记录缺少任务名（name/task/task_id）")
    start = _pick(row, _START_KEYS)
    end = _pick(row, _END_KEYS)
    if start is None or end is None:
        raise ValueError(f"任务 {name} 缺少 start/end 时间")
    return TaskInstance(
        name=str(name).strip(),
        start=_parse_ts(start, "start"),
        end=_parse_ts(end, "end"),
        deps=_parse_deps(_pick(row, _DEPS_KEYS)),
    )


def parse_instances(text: str) -> list[TaskInstance]:
    """Task instances from JSON (list of objects) or CSV text."""
    stripped = text.strip()
    if not stripped:
        raise ValueError("输入为空")
    rows: list[dict[str, Any]]
    if stripped[0] in "[{":
        data = json.loads(stripped)
        if isinstance(data, dict):     # {"tasks": [...]} wrapper
            for key in ("tasks", "task_instances", "instances", "data"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
        if not isinstance(data, list):
            raise ValueError("JSON 必须是任务实例数组（或含 tasks 数组的对象）")
        rows = [r for r in data if isinstance(r, dict)]
    else:
        rows = list(csv.DictReader(io.StringIO(stripped)))
    if len(rows) > MAX_INSTANCES:
        raise ValueError(f"任务实例超过上限 {MAX_INSTANCES}")
    return [_row_to_instance(r, i + 1) for i, r in enumerate(rows)]


def trace(instances: list[TaskInstance], target: str = "",
          deadline: str | None = None) -> SlaTrace:
    """Critical path + delay attribution for *target* (default: last end)."""
    if not instances:
        raise ValueError("没有任务实例")
    by_name = {t.name: t for t in instances}
    result = SlaTrace(target="", instances=len(instances))
    if len(by_name) < len(instances):
        result.warnings.append("存在重名任务实例，同名仅保留最后一条")
    if target:
        if target not in by_name:
            raise ValueError(f"目标任务不存在: {target}")
        tgt = by_name[target]
    else:
        tgt = max(instances, key=lambda t: t.end)
    result.target = tgt.name
    result.finished_at = tgt.end
    if deadline:
        result.deadline = _parse_ts(deadline, "deadline")
        result.breach_s = (tgt.end - result.deadline).total_seconds()

    run_start = min(t.start for t in instances)
    # walk upstream, always into the dependency that finished last
    path: list[PathStep] = []
    cur: TaskInstance | None = tgt
    seen: set[str] = set()
    while cur is not None and cur.name not in seen:
        seen.add(cur.name)
        deps = [by_name[d] for d in cur.deps if d in by_name]
        missing = [d for d in cur.deps if d not in by_name]
        if missing:
            result.warnings.append(
                f"任务 {cur.name} 的依赖缺少实例: {', '.join(missing)}")
        if deps:
            blocker = max(deps, key=lambda t: t.end)
            wait = (cur.start - blocker.end).total_seconds()
            path.append(PathStep(task=cur, wait_s=max(wait, 0.0),
                                 blocking=blocker.name))
            cur = blocker
        else:
            wait = (cur.start - run_start).total_seconds()
            path.append(PathStep(task=cur, wait_s=max(wait, 0.0)))
            cur = None
    if cur is not None:
        result.warnings.append("依赖图存在环，关键路径在环处截断")
    path.reverse()                      # upstream-first reading order
    result.path = path
    return result
