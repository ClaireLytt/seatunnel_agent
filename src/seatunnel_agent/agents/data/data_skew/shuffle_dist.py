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
        # cheap prefilter: skip the ~90% of events we never read
        if ('"SparkListenerTaskEnd"' not in raw
                and '"SparkListenerStage' not in raw):
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
            reads = per_stage.setdefault(sid, [])
            reads.append((int(info.get("Index") or len(reads)), read))
        elif kind in ("SparkListenerStageCompleted",
                      "SparkListenerStageSubmitted"):
            si = ev.get("Stage Info") or {}
            sid = int(si.get("Stage ID", -1))
            if sid >= 0 and si.get("Stage Name"):
                names[sid] = str(si["Stage Name"])

    dists: list[ShuffleDist] = []
    for sid, reads in per_stage.items():
        ordered = sorted(b for _, b in reads)
        if not ordered or ordered[-1] <= 0:
            continue
        n = len(ordered)
        p99 = ordered[min(n - 1, int(n * 0.99))]
        p50 = (ordered[n // 2] if n % 2
               else (ordered[n // 2 - 1] + ordered[n // 2]) / 2)
        dist = ShuffleDist(
            stage_id=sid, name=names.get(sid, ""), tasks=n,
            p50=float(p50), p99=float(p99), max=float(ordered[-1]),
            hot=sorted(reads, key=lambda ib: -ib[1])[:HOT_TOP_N])
        dists.append(dist)
    rank = {"confirmed": 0, "suspect": 1, "ok": 2}
    dists.sort(key=lambda d: (
        rank[d.verdict()],
        -(0.0 if d.ratio == float("inf") else d.ratio)))
    return dists


MAX_SALT = 64


def _salted_ok(p50: float, p99: float, factor: int) -> tuple[float, float,
                                                             bool]:
    """(new_p99, new_ratio, healthy?) after an N-way key salt.

    Model: the fat-tail tasks split N ways while the median task is
    unchanged — an upper bound on the remaining tail, since the split
    shares land on otherwise median-sized tasks.
    """
    new_p99 = max(p99 / factor, p50)
    ratio = new_p99 / p50 if p50 > 0 else float("inf")
    healthy = not (ratio >= SHUF_RATIO_SUSPECT
                   and new_p99 >= SHUF_MAX_SUSPECT)
    return new_p99, ratio, healthy


def salt_what_if(dists: list[ShuffleDist],
                 factor: int = 0) -> list[dict[str, Any]]:
    """Re-estimate the flagged stages under an N-way salt.

    ``factor`` >= 2 evaluates that salt; 0 searches the minimal factor
    (2..MAX_SALT) that brings each stage back under the suspect
    thresholds.  Healthy stages are skipped.
    """
    if factor and factor < 2:
        raise ValueError("salt factor must be >= 2 (0 = find minimal)")
    rows: list[dict[str, Any]] = []
    for d in dists:
        if d.verdict() == "ok":
            continue
        if factor:
            n = factor
            new_p99, ratio, healthy = _salted_ok(d.p50, d.p99, n)
        else:
            n, new_p99, ratio, healthy = 0, d.p99, d.ratio, False
            for cand in range(2, MAX_SALT + 1):
                new_p99, ratio, healthy = _salted_ok(d.p50, d.p99, cand)
                if healthy:
                    n = cand
                    break
        rows.append({
            "stage_id": d.stage_id, "name": d.name, "factor": n,
            "p99_before": d.p99, "p99_after": round(new_p99),
            "ratio_before": (0.0 if d.ratio == float("inf")
                             else round(d.ratio, 2)),
            "ratio_after": (0.0 if ratio == float("inf")
                            else round(ratio, 2)),
            "healthy": healthy,
        })
    return rows


def render_salt_what_if(rows: list[dict[str, Any]], lang: str) -> str:
    """Markdown section appended under the shuffle-dist table."""
    from seatunnel_agent.common.utils import md_table

    from .i18n import dsk

    lines = [f"### {dsk(lang, 'sw_title')}"]
    if not rows:
        lines.append(dsk(lang, "sw_none"))
        return "\n".join(lines)
    lines.extend(md_table(
        [dsk(lang, "sd_col_stage"), dsk(lang, "sw_col_factor"), "p99",
         "p99/p50", dsk(lang, "sw_col_after")],
        [[f"{r['stage_id']} {_stage_name(r['name'])}",
          f"x{r['factor']}" if r["factor"] else dsk(lang, "sw_not_enough"),
          f"{_fmt_bytes(r['p99_before'])} -> {_fmt_bytes(r['p99_after'])}",
          f"{r['ratio_before']:g}x -> {r['ratio_after']:g}x",
          dsk(lang, "sw_ok") if r["healthy"] else dsk(lang, "sw_still")]
         for r in rows]))
    lines.append("")
    lines.append(dsk(lang, "sw_hint"))
    factors = [r["factor"] for r in rows if r["healthy"] and r["factor"]]
    if factors:
        lines.append("")
        lines.append(f"**{dsk(lang, 'sw_sql_title')}**")
        lines.append("```sql")
        lines.append(salt_sql_template(max(factors)))
        lines.append("```")
    return "\n".join(lines)


def salt_sql_template(factor: int) -> str:
    """Ready-to-adapt Spark SQL skeleton for an N-way salted join."""
    n = max(2, int(factor))
    return (f"-- skewed (large) side: scatter each hot key {n} ways\n"
            f"SELECT *, concat(join_key, '#',\n"
            f"                 pmod(abs(hash(some_unique_col)), {n}))\n"
            f"         AS salted_key\n"
            f"FROM   big_table;\n"
            f"\n"
            f"-- other (small) side: explode every key into {n} copies\n"
            f"SELECT t.*, concat(t.join_key, '#', s.salt) AS salted_key\n"
            f"FROM   small_table t\n"
            f"LATERAL VIEW explode(sequence(0, {n - 1})) s AS salt;\n"
            f"\n"
            f"-- then join on salted_key instead of join_key")


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
