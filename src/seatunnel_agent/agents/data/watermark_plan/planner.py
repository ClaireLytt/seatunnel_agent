"""Deterministic watermark selection from observed event lateness.

Every Flink job asks the same question — "how many seconds of
out-of-orderness do we allow?" — and the answer is usually a guess.
Paste observed events — columns ``event_time`` and ``arrival_time``
(ISO datetimes, or ``HH:MM:SS``/``HH:MM`` all in one day; one format
per paste, the sla_board lesson) — and the plan measures instead:

* lateness distribution over arrival-vs-event (p50 / p95 / p99 / max)
  and the out-of-order share (events arriving after a later event
  already landed);
* the suggested bound: **p99 lateness plus a 25% margin** (minimum
  1 s), emitted as both the Flink SQL ``WATERMARK FOR`` clause and the
  ``forBoundedOutOfOrderness`` snippet, with the residual share the
  bound would still drop;
* WM001 — events arriving *before* their event time (clock skew;
  medium, high from 5% of rows);
* WM002 medium — a heavy tail (max lateness over 10x p99): a bigger
  watermark just adds latency, route stragglers to a side output;
* WM003 medium — stragglers later than one hour, counted.

rt_latency profiles pipeline stage latency; this sizes the event-time
watermark.  No cluster connection.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from seatunnel_agent.common.severity import severity_counts

__all__ = ["WatermarkPlan", "WatermarkFinding", "plan_watermark"]

_HMS_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")
_MARGIN = 1.25
_SKEW_HIGH = 0.05
_TAIL_RATIO = 10.0
_STRAGGLER_S = 3600.0


def _to_seconds(value: str, what: str) -> tuple[float, str]:
    v = (value or "").strip()
    m = _HMS_RE.match(v)
    if m:
        return (int(m.group(1)) * 3600 + int(m.group(2)) * 60
                + int(m.group(3) or 0)), "hm"
    try:
        from datetime import datetime

        return datetime.fromisoformat(v).timestamp(), "iso"
    except ValueError:
        raise ValueError(f"{what}: cannot parse time '{v}' "
                         "(use HH:MM[:SS] or an ISO datetime)")


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1,
              max(0, round(q * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


@dataclass
class WatermarkFinding:
    code: str            # WM001..WM003
    severity: str        # high | medium
    value: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity,
                "value": round(self.value, 4)}


@dataclass
class WatermarkPlan:
    events: int = 0
    out_of_order_share: float = 0.0
    p50_s: float = 0.0
    p95_s: float = 0.0
    p99_s: float = 0.0
    max_s: float = 0.0
    bound_s: int = 1
    residual_share: float = 0.0     # rows later than the bound
    sql_clause: str = ""
    java_snippet: str = ""
    findings: list[WatermarkFinding] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return severity_counts(self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"events": self.events,
                "out_of_order_share": round(self.out_of_order_share, 4),
                "p50_s": round(self.p50_s, 2),
                "p95_s": round(self.p95_s, 2),
                "p99_s": round(self.p99_s, 2),
                "max_s": round(self.max_s, 2),
                "bound_s": self.bound_s,
                "residual_share": round(self.residual_share, 4),
                "sql_clause": self.sql_clause,
                "java_snippet": self.java_snippet,
                "counts": self.counts(),
                "findings": [f.to_dict() for f in self.findings]}


def plan_watermark(headers: list[str],
                   rows: list[dict[str, str | None]]) -> WatermarkPlan:
    """Observed events → measured lateness + a watermark bound."""
    needed = {"event_time", "arrival_time"}
    missing = needed - {h.lower() for h in headers}
    if missing:
        raise ValueError("events need columns event_time/arrival_time — "
                         f"missing: {', '.join(sorted(missing))}")
    if len(rows) < 2:
        raise ValueError("need at least two events to measure lateness")
    col = {h.lower(): h for h in headers}

    parsed: list[tuple[float, float]] = []    # (arrival_s, event_s)
    fmt_seen: str | None = None
    for i, r in enumerate(rows):
        ev, f1 = _to_seconds(str(r.get(col["event_time"]) or ""),
                             f"row {i + 1} event_time")
        ar, f2 = _to_seconds(str(r.get(col["arrival_time"]) or ""),
                             f"row {i + 1} arrival_time")
        for fmt in (f1, f2):
            if fmt_seen is None:
                fmt_seen = fmt
            elif fmt != fmt_seen:
                raise ValueError(
                    f"row {i + 1}: the paste mixes HH:MM with ISO "
                    "datetimes — use one format per paste")
        parsed.append((ar, ev))
    parsed.sort(key=lambda t: t[0])

    plan = WatermarkPlan(events=len(parsed))
    lateness = [ar - ev for ar, ev in parsed]
    skew_rows = sum(1 for d in lateness if d < 0)
    late = sorted(d for d in lateness if d >= 0)

    max_event = float("-inf")
    out_of_order = 0
    for _, ev in parsed:
        if ev < max_event:
            out_of_order += 1
        max_event = max(max_event, ev)
    plan.out_of_order_share = out_of_order / len(parsed)

    # the bound targets the regular tail: stragglers past one hour
    # would otherwise drag p99 to max at small n (the rt_latency
    # lesson) and buy hours of latency for rows WM003 already routes
    # to a side output
    regular = [d for d in late if d <= _STRAGGLER_S]
    plan.p50_s = _percentile(regular, 0.5)
    plan.p95_s = _percentile(regular, 0.95)
    plan.p99_s = _percentile(regular, 0.99)
    plan.max_s = late[-1] if late else 0.0
    plan.bound_s = max(1, math.ceil(plan.p99_s * _MARGIN))
    plan.residual_share = (sum(1 for d in late if d > plan.bound_s)
                           / len(parsed))
    plan.sql_clause = (f"WATERMARK FOR event_time AS event_time - "
                       f"INTERVAL '{plan.bound_s}' SECOND")
    plan.java_snippet = (
        "WatermarkStrategy.<T>forBoundedOutOfOrderness("
        f"Duration.ofSeconds({plan.bound_s}))")

    if skew_rows:
        share = skew_rows / len(parsed)
        plan.findings.append(WatermarkFinding(
            "WM001", "high" if share >= _SKEW_HIGH else "medium", share))
    if late and plan.p99_s > 0 and plan.max_s / plan.p99_s >= _TAIL_RATIO:
        plan.findings.append(WatermarkFinding(
            "WM002", "medium", round(plan.max_s / plan.p99_s, 1)))
    stragglers = sum(1 for d in late if d > _STRAGGLER_S)
    if stragglers:
        plan.findings.append(WatermarkFinding(
            "WM003", "medium", stragglers))

    order = {"high": 0, "medium": 1}
    plan.findings.sort(key=lambda f: (order[f.severity], f.code))
    return plan
