"""Shuffle-read distribution anomalies from a Spark event log.

The runtime diagnosis flags straggler stages via max/median duration
and shuffle bytes; this add-on looks one level deeper at the *shape*
of each stage's shuffle-read distribution:

* p50 / p99 / max bytes per task,
* the p99/p50 skew ratio (reusing the runtime thresholds:
  >= 3x suspect, >= 5x confirmed, gated by the same absolute minimums),
* the hottest task indices with their byte counts.

A stage can look healthy on max/median yet hide a fat tail — p99
catches the "several hot partitions" pattern that a single max misses.
Event-log mode only (the History Server summaries do not expose the
full per-task vector).
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .runtime import (
    MIN_TASKS,
    SHUF_MAX_CONFIRMED,
    SHUF_MAX_SUSPECT,
    SHUF_RATIO_CONFIRMED,
    SHUF_RATIO_SUSPECT,
    _fmt_bytes,
    _iter_eventlog_lines,
    _stage_name,
)

HOT_TOP_N = 5


@dataclass
class ShuffleDist:
    stage_id: int
    name: str = ""
    tasks: int = 0
    p50: float = 0.0
    p99: float = 0.0
    max: float = 0.0
    hot: list[tuple[int, float]] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        if self.p99 <= 0:
            return 0.0
        return self.p99 / self.p50 if self.p50 > 0 else float("inf")

    def verdict(self) -> str:
        if self.tasks < MIN_TASKS:
            return "ok"
        if self.ratio >= SHUF_RATIO_CONFIRMED and self.p99 >= SHUF_MAX_CONFIRMED:
            return "confirmed"
        if self.ratio >= SHUF_RATIO_SUSPECT and self.p99 >= SHUF_MAX_SUSPECT:
            return "suspect"
        return "ok"

    def to_dict(self) -> dict[str, Any]:
        return {"stage_id": self.stage_id, "name": self.name,
                "tasks": self.tasks, "p50": self.p50, "p99": self.p99,
                "max": self.max,
                "ratio": (0.0 if self.ratio == float("inf")
                          else round(self.ratio, 2)),
                "verdict": self.verdict(),
                "hot": [[i, b] for i, b in self.hot]}


def shuffle_distribution(path: str | Path) -> list[ShuffleDist]:
    """Per-stage shuffle-read distributions, worst ratio first."""
    per_stage: dict[int, list[tuple[int, float]]] = {}
    names: dict[int, str] = {}
    for raw in _iter_eventlog_lines(Path(path)):
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except ValueError:
            continue
        kind = str(ev.get("Event", ""))
        if kind == "SparkListenerTaskEnd":
            info = ev.get("Task Info") or {}
            if info.get("Failed") or info.get("Killed"):
                continue
            sid = int(ev.get("Stage ID", -1))
            if sid < 0:
                continue
            metrics = ev.get("Task Metrics") or {}
            sr = metrics.get("Shuffle Read Metrics") or {}
            read = (float(sr.get("Remote Bytes Read") or 0)
                    + float(sr.get("Local Bytes Read") or 0))
            per_stage.setdefault(sid, []).append(
                (int(info.get("Index") or len(per_stage.get(sid, []))),
                 read))
        elif kind in ("SparkListenerStageCompleted",
                      "SparkListenerStageSubmitted"):
            si = ev.get("Stage Info") or {}
            sid = int(si.get("Stage ID", -1))
            if sid >= 0 and si.get("Stage Name"):
                names[sid] = str(si["Stage Name"])

    dists: list[ShuffleDist] = []
    for sid, reads in per_stage.items():
        values = [b for _, b in reads]
        if not values or max(values) <= 0:
            continue
        ordered = sorted(values)
        p99 = ordered[min(len(ordered) - 1,
                          int(len(ordered) * 0.99))]
        dist = ShuffleDist(
            stage_id=sid, name=names.get(sid, ""), tasks=len(values),
            p50=float(statistics.median(values)), p99=float(p99),
            max=float(max(values)),
            hot=sorted(reads, key=lambda ib: -ib[1])[:HOT_TOP_N])
        dists.append(dist)
    rank = {"confirmed": 0, "suspect": 1, "ok": 2}
    dists.sort(key=lambda d: (
        rank[d.verdict()],
        -(0.0 if d.ratio == float("inf") else d.ratio)))
    return dists


def render_shuffle_dist(dists: list[ShuffleDist], lang: str) -> str:
    """Markdown section appended under the runtime diagnosis."""
    from .i18n import dsk

    lines = [f"### {dsk(lang, 'sd_title')}"]
    flagged = [d for d in dists if d.verdict() != "ok"]
    if not flagged:
        lines.append(dsk(lang, "sd_all_ok"))
        return "\n".join(lines)
    lines.append(f"| {dsk(lang, 'sd_col_stage')} "
                 f"| {dsk(lang, 'sd_col_tasks')} "
                 f"| p50 | p99 | p99/p50 "
                 f"| {dsk(lang, 'sd_col_verdict')} "
                 f"| {dsk(lang, 'sd_col_hot')} |")
    lines.append("|---|---|---|---|---|---|---|")
    for d in flagged:
        hot = ", ".join(f"#{i} {_fmt_bytes(b)}" for i, b in d.hot[:3])
        ratio = "∞" if d.ratio == float("inf") else f"{d.ratio:.1f}x"
        lines.append(
            f"| {d.stage_id} {_stage_name(d.name)} | {d.tasks} "
            f"| {_fmt_bytes(d.p50)} | {_fmt_bytes(d.p99)} | {ratio} "
            f"| {dsk(lang, 'sd_' + d.verdict())} | {hot} |")
    lines.append("")
    lines.append(dsk(lang, "sd_hint"))
    return "\n".join(lines)
