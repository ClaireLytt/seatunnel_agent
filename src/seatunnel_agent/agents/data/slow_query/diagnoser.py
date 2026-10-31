"""Deterministic slow-query root-cause diagnoser.

Input: one run's execution metrics (JSON — duration, scan/shuffle
bytes, GC and queue time, per-stage task max/median and spill), plus an
optional history baseline (jsonl, one entry per past run, the same
format the trend watchers write).  The rules rank the likely root
causes and each verdict carries a prescription that points at the
sibling agent that fixes it:

  SQ001 skew            stage task max/median >= 5x          → data_skew
  SQ002 scan blow-up    scan bytes >= 2x the baseline median → sql_perf
  SQ003 shuffle spill   spill bytes > 0                      → sql_cost
  SQ004 GC pressure     GC time >= 20% of the duration
  SQ005 queue wait      queue time >= 30% of the duration    → dag_conflict
  SQ006 small files     mean input per task < 8 MB over many tasks

A duration-regression header compares the run against the baseline
median when history is given.  No cluster connection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from statistics import median
from typing import Any

SKEW_RATIO = 5.0
SCAN_BLOWUP = 2.0
GC_SHARE = 0.2
QUEUE_SHARE = 0.3
SMALL_FILE_BYTES = 8 * 1024 * 1024
SMALL_FILE_MIN_TASKS = 200


@dataclass
class StageMetrics:
    stage: str
    task_max_s: float = 0.0
    task_median_s: float = 0.0
    spill_bytes: int = 0
    input_bytes: int = 0
    tasks: int = 0


@dataclass
class RunMetrics:
    name: str = "query"
    duration_s: float = 0.0
    scan_bytes: int = 0
    shuffle_bytes: int = 0
    gc_s: float = 0.0
    queue_s: float = 0.0
    stages: list[StageMetrics] = field(default_factory=list)


def parse_metrics(text: str) -> RunMetrics:
    stripped = (text or "").strip()
    if not stripped:
        raise ValueError("empty metrics")
    data = json.loads(stripped)
    if not isinstance(data, dict):
        raise ValueError("metrics must be a JSON object")
    if not data.get("duration_s"):
        raise ValueError("metrics need 'duration_s'")
    run = RunMetrics(
        name=str(data.get("name") or data.get("query_id") or "query"),
        duration_s=float(data["duration_s"]),
        scan_bytes=int(data.get("scan_bytes") or 0),
        shuffle_bytes=int(data.get("shuffle_bytes") or 0),
        gc_s=float(data.get("gc_s") or 0),
        queue_s=float(data.get("queue_s") or 0))
    for i, st in enumerate(data.get("stages") or []):
        run.stages.append(StageMetrics(
            stage=str(st.get("stage") or st.get("id") or i),
            task_max_s=float(st.get("task_max_s") or 0),
            task_median_s=float(st.get("task_median_s") or 0),
            spill_bytes=int(st.get("spill_bytes") or 0),
            input_bytes=int(st.get("input_bytes") or 0),
            tasks=int(st.get("tasks") or 0)))
    return run


def parse_baseline(text: str) -> list[dict[str, Any]]:
    """jsonl of past runs (ts/duration_s/scan_bytes...) → entries."""
    entries = []
    for line in (text or "").splitlines():
        if line.strip():
            entry = json.loads(line)
            if isinstance(entry, dict):
                entries.append(entry)
    return entries


@dataclass
class Cause:
    code: str
    share: float            # estimated share of the slowdown, 0..1
    detail: str
    refer: str              # the sibling agent that fixes it ("" = none)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "share": round(self.share, 3),
                "detail": self.detail, "refer": self.refer}


@dataclass
class Diagnosis:
    name: str
    duration_s: float
    baseline_median_s: float = 0.0   # 0: no baseline given
    causes: list[Cause] = field(default_factory=list)

    @property
    def regression(self) -> float:
        if not self.baseline_median_s:
            return 0.0
        return round(self.duration_s / self.baseline_median_s, 2)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "duration_s": self.duration_s,
                "baseline_median_s": self.baseline_median_s,
                "regression": self.regression,
                "causes": [c.to_dict() for c in self.causes]}


def diagnose(run: RunMetrics,
             baseline: list[dict[str, Any]] | None = None) -> Diagnosis:
    diag = Diagnosis(name=run.name, duration_s=run.duration_s)
    add = diag.causes.append

    worst_skew = 0.0
    worst_st: StageMetrics | None = None
    for st in run.stages:
        if st.task_median_s > 0:
            ratio = st.task_max_s / st.task_median_s
            if ratio > worst_skew:
                worst_skew, worst_st = ratio, st
    if worst_st is not None and worst_skew >= SKEW_RATIO:
        # the straggler holds the stage: its excess over the median is
        # the share of the run it wasted
        excess = min((worst_st.task_max_s - worst_st.task_median_s)
                     / run.duration_s, 1.0)
        add(Cause("SQ001", excess,
                  f"stage {worst_st.stage}: max/median = {worst_skew:.1f}x",
                  "data_skew"))

    durations = [float(e["duration_s"]) for e in (baseline or [])
                 if e.get("duration_s")]
    if durations:
        diag.baseline_median_s = round(median(durations), 2)
    scans = [int(e["scan_bytes"]) for e in (baseline or [])
             if e.get("scan_bytes")]
    if scans and run.scan_bytes:
        base_scan = median(scans)
        if base_scan and run.scan_bytes >= SCAN_BLOWUP * base_scan:
            ratio = run.scan_bytes / base_scan
            add(Cause("SQ002", min((ratio - 1) / ratio, 1.0),
                      f"scan {ratio:.1f}x the baseline median", "sql_perf"))

    spill = sum(st.spill_bytes for st in run.stages)
    if spill:
        add(Cause("SQ003", 0.3,
                  f"spill {spill / (1 << 30):.1f} GB", "sql_cost"))
    if run.duration_s and run.gc_s / run.duration_s >= GC_SHARE:
        add(Cause("SQ004", run.gc_s / run.duration_s,
                  f"GC {run.gc_s / run.duration_s:.0%} of the run", ""))
    if run.duration_s and run.queue_s / run.duration_s >= QUEUE_SHARE:
        add(Cause("SQ005", run.queue_s / run.duration_s,
                  f"queued {run.queue_s / run.duration_s:.0%} of the run",
                  "dag_conflict"))
    for st in run.stages:
        if (st.tasks >= SMALL_FILE_MIN_TASKS and st.input_bytes
                and st.input_bytes / st.tasks < SMALL_FILE_BYTES):
            add(Cause(
                "SQ006", 0.2,
                f"stage {st.stage}: {st.tasks} tasks, "
                f"{st.input_bytes / st.tasks / (1 << 20):.1f} MB/task", ""))
            break

    diag.causes.sort(key=lambda c: (-c.share, c.code))
    return diag
