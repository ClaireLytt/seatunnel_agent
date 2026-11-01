"""Backfill plan over update events x lineage.

Input model: the freshness agent's per-table update events (JSON/CSV)
and rules, plus an optional lineage graph built from a SQL directory.

Per table with a known cadence (rule or inferred median gap):

* pick the **partition grid** — daily buckets for cadences around a day
  or longer (stepping ``round(interval/1d)`` days), hourly buckets for
  sub-day cadences (stepping ``round(interval/1h)`` hours); cadences
  under 45 minutes are skipped (too fine for calendar backfill),
* **missing slots** = expected buckets minus observed buckets, anchored
  at the first observed update; the current bucket counts as expected
  only once *now* has passed the table's typical in-bucket arrival
  offset plus a grace of a quarter interval,
* **cascade** — every missing slot propagates through the lineage's
  downstream closure: downstream tables must re-run for those dates even
  when their own output landed.

The plan orders impacted tables into topological batches (upstream
first); *now* defaults to the latest update seen, so runs reproduce.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from statistics import median
from typing import Any

MAX_SLOTS_PER_TABLE = 1000
GRACE_SHARE = 0.25          # quarter of the cadence
MIN_INTERVAL_S = 45 * 60    # below this, calendar backfill is meaningless
DAILY_CUTOVER_S = 0.75 * 86400.0
MULTIDAY_CUTOVER_S = 1.75 * 86400.0


@dataclass
class TablePlan:
    table: str
    missing: list[str] = field(default_factory=list)   # own gaps, slot labels
    cascade: list[str] = field(default_factory=list)   # rerun for upstream gaps
    from_upstream: list[str] = field(default_factory=list)
    batch: int = 0                                     # 1-based topo batch
    in_inventory: bool = True
    granularity: str = "day"                           # "day" | "hour"

    @property
    def dates(self) -> list[str]:
        return sorted(set(self.missing) | set(self.cascade))

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "batch": self.batch,
            "missing": list(self.missing),
            "cascade": list(self.cascade),
            "from_upstream": list(self.from_upstream),
            "in_inventory": self.in_inventory,
            "granularity": self.granularity,
        }


@dataclass
class BackfillPlan:
    now: datetime
    tables: list[TablePlan] = field(default_factory=list)  # batch order
    skipped: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_slots(self) -> int:
        return sum(len(t.dates) for t in self.tables)

    @property
    def batches(self) -> int:
        return max((t.batch for t in self.tables), default=0)

    def commands(self, template: str) -> list[str]:
        """One rendered command per (table, slot), batch order."""
        out = []
        for t in self.tables:
            for d in t.dates:
                out.append(template.replace("{table}", t.table)
                           .replace("{date}", d))
        return out


def _bucket(dt: datetime, granularity: str) -> datetime:
    if granularity == "day":
        return datetime(dt.year, dt.month, dt.day)
    return datetime(dt.year, dt.month, dt.day, dt.hour)


def _label(bucket: datetime, granularity: str) -> str:
    if granularity == "day":
        return bucket.date().isoformat()
    return bucket.strftime("%Y-%m-%d %H:00")


def _granularity(interval_s: float) -> tuple[str, timedelta] | None:
    """(granularity, grid step) for a cadence, None when too fine."""
    if interval_s < MIN_INTERVAL_S:
        return None
    if interval_s >= MULTIDAY_CUTOVER_S:
        return "day", timedelta(days=max(1, round(interval_s / 86400.0)))
    if interval_s >= DAILY_CUTOVER_S:
        return "day", timedelta(days=1)
    return "hour", timedelta(hours=max(1, round(interval_s / 3600.0)))


def _typical_offset(updates: list[datetime], granularity: str) -> timedelta:
    """Median in-bucket arrival offset (time-of-day / minute-of-hour)."""
    offs = [(u - _bucket(u, granularity)).total_seconds() for u in updates]
    return timedelta(seconds=median(offs))


def missing_slots(updates: list[datetime], interval_s: float,
                  now: datetime, since: datetime | None = None,
                  ) -> tuple[list[str], str] | None:
    """Missing slot labels for one table, or None when the cadence is
    too fine for calendar buckets. Raises on slot-count blowups."""
    grid = _granularity(interval_s)
    if grid is None:
        return None
    granularity, step = grid
    observed = {_bucket(u, granularity) for u in updates}
    start = min(observed)
    if since is not None:
        start = max(start, _bucket(since, granularity))
    # the current bucket is only due after the typical arrival + grace
    deadline = (_typical_offset(updates, granularity)
                + timedelta(seconds=GRACE_SHARE * interval_s))
    missing: list[str] = []
    cur = start
    while cur <= _bucket(now, granularity):
        if cur not in observed and cur + deadline <= now:
            missing.append(_label(cur, granularity))
            if len(missing) > MAX_SLOTS_PER_TABLE:
                raise ValueError(
                    f"缺失分区超过上限 {MAX_SLOTS_PER_TABLE}，请用 since 缩小窗口")
        cur += step
    return missing, granularity


def compact_ranges(labels: list[str]) -> str:
    """'05-01, 05-02, 05-03, 05-05' -> '2024-05-01..2024-05-03, 2024-05-05'
    (daily labels only; anything else joins verbatim)."""
    runs: list[str] = []
    i, n = 0, len(labels)
    while i < n:
        j = i
        try:
            while (j + 1 < n
                   and date.fromisoformat(labels[j + 1])
                   == date.fromisoformat(labels[j]) + timedelta(days=1)):
                j += 1
        except ValueError:
            pass
        runs.append(labels[i] if j == i else f"{labels[i]}..{labels[j]}")
        i = j + 1
    return ", ".join(runs)


def _topo_batches(tables: list[str], upstream: dict[str, set[str]],
                  ) -> tuple[dict[str, int], list[str]]:
    """Kahn batches over the impacted subgraph; leftovers are a cycle."""
    impacted = set(tables)
    deps = {t: {u for u in upstream.get(t, ()) if u in impacted}
            for t in impacted}
    batch_of: dict[str, int] = {}
    batch = 0
    while deps:
        ready = sorted(t for t, ds in deps.items() if not ds)
        if not ready:
            break
        batch += 1
        for t in ready:
            batch_of[t] = batch
            del deps[t]
        for ds in deps.values():
            ds.difference_update(ready)
    return batch_of, sorted(deps)


def plan(events: dict[str, list[datetime]],
         rules: dict[str, dict[str, float]] | None = None,
         graph: Any | None = None,
         now: str | None = None,
         since: str | None = None) -> BackfillPlan:
    """Backfill plan: own gaps per table + downstream cascade, in
    topological batches. *graph* is a data_lineage ``LineageGraph``."""
    # local import: shares the freshness agent's parsing/inference
    from seatunnel_agent.agents.data.data_freshness.checker import (
        _infer_interval,
        _match_rule,
        _parse_ts,
    )

    if not events:
        raise ValueError("没有更新事件")
    rules = rules or {}
    at = _parse_ts(now, "now") if now else max(u[-1] for u in events.values())
    lo = _parse_ts(since, "since") if since else None
    result = BackfillPlan(now=at)

    own: dict[str, TablePlan] = {}
    for table in sorted(events):
        updates = [u for u in events[table] if u <= at]
        if not updates:
            result.skipped.append((table, "no_updates_before_now"))
            continue
        rule = _match_rule(table, rules)
        interval = rule.get("interval_s") or _infer_interval(updates)
        if not interval:
            result.skipped.append((table, "no_cadence"))
            continue
        slots = missing_slots(updates, interval, at, since=lo)
        if slots is None:
            result.skipped.append((table, "cadence_too_fine"))
            continue
        missing, granularity = slots
        if missing:
            own[table] = TablePlan(table=table, missing=missing,
                                   granularity=granularity)

    # cascade through the downstream closure (date sets only grow -> fixpoint)
    downstream: dict[str, set[str]] = getattr(graph, "downstream", {}) or {}
    upstream: dict[str, set[str]] = getattr(graph, "upstream", {}) or {}
    impact: dict[str, set[str]] = {t: set(p.missing) for t, p in own.items()}
    contributors: dict[str, set[str]] = {}
    work = list(own)
    while work:
        src = work.pop()
        for dst in sorted(downstream.get(src, ())):
            added = impact[src] - impact.setdefault(dst, set())
            contributors.setdefault(dst, set()).add(src)
            if added:
                impact[dst] |= added
                work.append(dst)

    for table, dates in impact.items():
        tp = own.get(table) or TablePlan(table=table,
                                         in_inventory=table in events)
        tp.cascade = sorted(dates - set(tp.missing))
        tp.from_upstream = sorted(contributors.get(table, ()))
        own[table] = tp

    batch_of, cyclic = _topo_batches(list(own), upstream)
    if cyclic:
        last = max(batch_of.values(), default=0) + 1
        for t in cyclic:
            batch_of[t] = last
        result.warnings.append(
            f"血缘存在环，以下表放入最后一批: {', '.join(cyclic)}")
    for t, tp in own.items():
        tp.batch = batch_of[t]
    result.tables = sorted(own.values(), key=lambda p: (p.batch, p.table))

    not_in_inventory = [t.table for t in result.tables if not t.in_inventory]
    if not_in_inventory:
        result.warnings.append(
            "以下级联表不在更新清单中，日期沿用上游缺口: "
            + ", ".join(not_in_inventory))
    if result.skipped:
        result.warnings.append(
            f"{len(result.skipped)} 张表无法判定节奏或粒度，已跳过")
    return result


def plan_to_dict(result: BackfillPlan) -> dict[str, Any]:
    return {
        "now": result.now.isoformat(sep=" "),
        "batches": result.batches,
        "total_slots": result.total_slots,
        "tables": [t.to_dict() for t in result.tables],
        "skipped": [{"table": t, "reason": r} for t, r in result.skipped],
        "warnings": list(result.warnings),
    }
