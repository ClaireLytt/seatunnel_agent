"""Deterministic end-to-end latency analysis over event timestamps.

Input is per-event timestamp rows — CSV with a header or JSONL — where
each row carries an event id and the timestamps of the stages it passed
(``produce_ts, ingest_ts, process_ts, sink_ts``; later stages may be
missing and extra stages are accepted in column order).  Timestamps are
ISO datetimes or epoch millis.  Per stage hop and end-to-end, the
analyzer reports p50/p95/max, names the dominant stage (where the p95
time actually goes), lists the outlier events (end-to-end above 3x the
median, with their worst hop), and counts SLA breaches against a
threshold.  No connection to anything.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime

__all__ = ["LatencyResult", "StageStats", "analyze_latency",
           "parse_events"]

_DEFAULT_STAGES = ("produce_ts", "ingest_ts", "process_ts", "sink_ts")
_OUTLIER_K = 3.0


@dataclass
class StageStats:
    hop: str              # "produce→ingest"
    count: int
    p50_ms: float
    p95_ms: float
    max_ms: float

    def to_dict(self) -> dict:
        return {"hop": self.hop, "count": self.count,
                "p50_ms": round(self.p50_ms, 1),
                "p95_ms": round(self.p95_ms, 1),
                "max_ms": round(self.max_ms, 1)}


@dataclass
class LatencyResult:
    events: int
    stages: list[StageStats]
    e2e: StageStats | None
    dominant_hop: str
    outliers: list[dict] = field(default_factory=list)
    sla_ms: float = 0.0
    breaches: int = 0

    def to_dict(self) -> dict:
        return {"events": self.events,
                "stages": [s.to_dict() for s in self.stages],
                "e2e": self.e2e.to_dict() if self.e2e else None,
                "dominant_hop": self.dominant_hop,
                "outliers": self.outliers,
                "sla_ms": self.sla_ms, "breaches": self.breaches}


def _to_ms(value) -> float | None:
    if value in (None, ""):
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        num = float(s)
        # epoch seconds vs millis: anything before ~2001 in ms is seconds
        return num * 1000.0 if num < 10_000_000_000 else num
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s).timestamp() * 1000.0
    except ValueError as exc:
        raise ValueError(f"bad timestamp '{s}'") from exc


def parse_events(text: str) -> tuple[list[str], list[dict]]:
    """Rows → (ordered stage columns, events with ms timestamps)."""
    body = (text or "").strip()
    if not body:
        raise ValueError("empty input / 输入为空")
    if body.lstrip()[:1] in "{[":
        items = (json.loads(body) if body.lstrip().startswith("[")
                 else [json.loads(ln) for ln in body.splitlines()
                       if ln.strip()])
        rows = [dict(it) for it in items]
        header: list[str] = []
        for r in rows:
            for k in r:
                if k not in header:
                    header.append(k)
    else:
        reader = csv.DictReader(io.StringIO(body))
        rows = [dict(r) for r in reader]
        header = list(reader.fieldnames or ())
    stages = [c for c in header if c.endswith("_ts")]
    if len(stages) < 2:
        raise ValueError("need at least two *_ts stage columns / "
                         "至少需要两个 *_ts 阶段列")
    events = []
    for i, row in enumerate(rows, start=1):
        ev = {"event_id": str(row.get("event_id") or row.get("id") or i)}
        for s in stages:
            try:
                ev[s] = _to_ms(row.get(s))
            except ValueError as exc:
                raise ValueError(f"row {i}: {exc}") from exc
        events.append(ev)
    if not events:
        raise ValueError("no event rows / 没有事件行")
    return stages, events


def _pct(xs: list[float], q: float) -> float:
    s = sorted(xs)
    idx = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[idx]


def _stats(hop: str, xs: list[float]) -> StageStats:
    return StageStats(hop=hop, count=len(xs), p50_ms=_pct(xs, 0.5),
                      p95_ms=_pct(xs, 0.95), max_ms=max(xs))


def analyze_latency(stages: list[str], events: list[dict],
                    sla_ms: float = 0.0) -> LatencyResult:
    hop_values: dict[str, list[float]] = {}
    e2e_values: list[tuple[str, float, dict[str, float]]] = []
    for ev in events:
        present = [(s, ev[s]) for s in stages if ev.get(s) is not None]
        hops: dict[str, float] = {}
        for (a, ta), (b, tb) in zip(present, present[1:]):
            hop = f"{a[:-3]}→{b[:-3]}"
            delta = max(0.0, tb - ta)
            hops[hop] = delta
            hop_values.setdefault(hop, []).append(delta)
        if len(present) >= 2:
            total = max(0.0, present[-1][1] - present[0][1])
            e2e_values.append((ev["event_id"], total, hops))

    stage_stats = [_stats(h, xs) for h, xs in hop_values.items()]
    # keep pipeline order
    order = {f"{a[:-3]}→{b[:-3]}": i
             for i, (a, b) in enumerate(zip(stages, stages[1:]))}
    stage_stats.sort(key=lambda s: order.get(s.hop, 99))

    e2e = (_stats("end→end", [t for _, t, _ in e2e_values])
           if e2e_values else None)
    dominant = (max(stage_stats, key=lambda s: s.p95_ms).hop
                if stage_stats else "")

    outliers: list[dict] = []
    if e2e and len(e2e_values) >= 4:
        # 3x the MEDIAN: a single huge event inflates p95 at small n
        cut = _OUTLIER_K * e2e.p50_ms
        for eid, total, hops in e2e_values:
            if total > cut and hops:
                worst = max(hops.items(), key=lambda kv: kv[1])
                outliers.append({"event_id": eid,
                                 "e2e_ms": round(total, 1),
                                 "worst_hop": worst[0],
                                 "worst_ms": round(worst[1], 1)})
        outliers.sort(key=lambda o: -o["e2e_ms"])
        outliers = outliers[:5]

    breaches = (sum(1 for _, t, _ in e2e_values if t > sla_ms)
                if sla_ms > 0 else 0)
    return LatencyResult(events=len(events), stages=stage_stats, e2e=e2e,
                         dominant_hop=dominant, outliers=outliers,
                         sla_ms=sla_ms, breaches=breaches)
