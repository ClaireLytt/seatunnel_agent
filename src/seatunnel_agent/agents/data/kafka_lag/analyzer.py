"""Deterministic Kafka consumer-lag diagnosis from a group snapshot.

Input is one consumer group's offset snapshot — JSON::

    {"group": "g-orders",
     "topics": [{"topic": "orders",
                 "partitions": [{"partition": 0,
                                 "log_end_offset": 120000,
                                 "committed_offset": 80000,
                                 "consume_rate": 500,
                                 "produce_rate": 800}]}]}

or flat CSV rows (``topic,partition,log_end_offset,committed_offset,
consume_rate,produce_rate``).  Rules flag the total backlog, hot
partitions (max lag far above the median — a key-skew or stuck-consumer
smell), partitions where consumption trails production (with the
catch-up ETA when it does not), and stalled partitions (zero consume
rate with lag).  Rates are per second and optional — rate rules simply
stay quiet without them.  No broker connection.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field

__all__ = ["KafkaFinding", "LagResult", "PartitionLag", "analyze_lag",
           "lag_trend", "parse_lag_snapshot"]

_TOTAL_LAG = (100_000, 1_000_000)
_HOT_RATIO = (5.0, 20.0)       # max lag vs median lag
_ETA_MIN = (30.0, 180.0)       # catch-up minutes


@dataclass
class PartitionLag:
    topic: str
    partition: int
    log_end_offset: int
    committed_offset: int
    consume_rate: float | None = None
    produce_rate: float | None = None

    @property
    def lag(self) -> int:
        return max(0, self.log_end_offset - self.committed_offset)

    def to_dict(self) -> dict:
        return {"topic": self.topic, "partition": self.partition,
                "log_end_offset": self.log_end_offset,
                "committed_offset": self.committed_offset,
                "consume_rate": self.consume_rate,
                "produce_rate": self.produce_rate, "lag": self.lag}


@dataclass
class KafkaFinding:
    code: str          # KL001..
    severity: str      # high / mid / low
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail}


@dataclass
class LagResult:
    group: str
    total_lag: int
    partitions: list[PartitionLag]
    findings: list[KafkaFinding]

    def to_dict(self) -> dict:
        return {"group": self.group, "total_lag": self.total_lag,
                "partitions": [p.to_dict() for p in self.partitions],
                "findings": [f.to_dict() for f in self.findings]}


def _num(value, default=None):
    if value in (None, ""):
        return default
    return float(value)


def parse_lag_snapshot(text: str) -> tuple[str, list[PartitionLag]]:
    body = (text or "").strip()
    if not body:
        raise ValueError("empty snapshot / 快照为空")
    parts: list[PartitionLag] = []
    group = ""
    if body.startswith("{"):
        snap = json.loads(body)
        group = str(snap.get("group") or "")
        for t in snap.get("topics") or ():
            topic = str(t.get("topic") or "?")
            for p in t.get("partitions") or ():
                parts.append(PartitionLag(
                    topic=topic, partition=int(p.get("partition") or 0),
                    log_end_offset=int(p.get("log_end_offset") or 0),
                    committed_offset=int(p.get("committed_offset") or 0),
                    consume_rate=_num(p.get("consume_rate")),
                    produce_rate=_num(p.get("produce_rate"))))
    else:
        for i, row in enumerate(csv.DictReader(io.StringIO(body)), start=1):
            if not (row.get("topic") or "").strip():
                raise ValueError(f"row {i}: needs 'topic'")
            parts.append(PartitionLag(
                topic=row["topic"].strip(),
                partition=int(row.get("partition") or 0),
                log_end_offset=int(row.get("log_end_offset") or 0),
                committed_offset=int(row.get("committed_offset") or 0),
                consume_rate=_num(row.get("consume_rate")),
                produce_rate=_num(row.get("produce_rate"))))
    if not parts:
        raise ValueError("no partitions in the snapshot / 快照里没有分区")
    return group, parts


def lag_trend(entries: list[dict], n: int) -> dict | None:
    """Sustained backlog growth over the last *n* ledger snapshots.

    Returns the trend facts when the last ``n`` recorded total lags rise
    strictly snapshot over snapshot — the pattern a single-snapshot gate
    misses because each step stays under its threshold.  ``None`` when
    the ledger is shorter than ``n`` or any step held or shrank (the
    backlog is draining).  Mirrors slow_query.detect_trend, keyed on
    ``total_lag``.
    """
    if n < 2:
        raise ValueError("trend window must be >= 2 snapshots")
    lags = [float(e["total_lag"]) for e in entries
            if isinstance(e.get("total_lag"), (int, float))]
    if len(lags) < n:
        return None
    window = lags[-n:]
    if any(b <= a for a, b in zip(window, window[1:])):
        return None
    return {"snapshots": n, "from_lag": int(window[0]),
            "to_lag": int(window[-1]),
            "growth_pct": round(100 * (window[-1] / window[0] - 1), 1)
            if window[0] else None}


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _grade(value: float, thresholds: tuple[float, float]) -> str | None:
    mid, high = thresholds
    if value >= high:
        return "high"
    if value >= mid:
        return "mid"
    return None


def analyze_lag(group: str, parts: list[PartitionLag]) -> LagResult:
    findings: list[KafkaFinding] = []
    total = sum(p.lag for p in parts)

    # KL001 total backlog
    sev = _grade(total, _TOTAL_LAG)
    if sev:
        findings.append(KafkaFinding("KL001", sev, {
            "total_lag": total, "partitions": len(parts)}))

    # KL002 hot partition: key skew or one stuck consumer
    lags = [float(p.lag) for p in parts]
    med = _median(lags)
    if med > 0 and len(parts) >= 2:
        worst = max(parts, key=lambda p: p.lag)
        ratio = worst.lag / med
        sev = _grade(ratio, _HOT_RATIO)
        if sev:
            findings.append(KafkaFinding("KL002", sev, {
                "topic": worst.topic, "partition": worst.partition,
                "lag": worst.lag, "median_lag": int(med),
                "ratio": round(ratio, 1)}))

    # KL003 falling behind / catch-up ETA; KL004 stalled
    behind: list[dict] = []
    for p in parts:
        if p.consume_rate is None:
            continue
        if p.consume_rate <= 0 and p.lag > 0:
            findings.append(KafkaFinding("KL004", "high", {
                "topic": p.topic, "partition": p.partition, "lag": p.lag}))
            continue
        if p.produce_rate is None or p.lag == 0:
            continue
        net = p.consume_rate - p.produce_rate
        if net <= 0:
            behind.append({"topic": p.topic, "partition": p.partition,
                           "lag": p.lag, "consume_rate": p.consume_rate,
                           "produce_rate": p.produce_rate})
        else:
            eta_min = p.lag / net / 60.0
            sev = _grade(eta_min, _ETA_MIN)
            if sev:
                findings.append(KafkaFinding("KL005", sev, {
                    "topic": p.topic, "partition": p.partition,
                    "lag": p.lag, "eta_min": round(eta_min, 1)}))
    if behind:
        behind.sort(key=lambda b: -b["lag"])
        findings.append(KafkaFinding("KL003", "high", {
            "count": len(behind), "top": behind[:3]}))

    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code))
    parts_sorted = sorted(parts, key=lambda p: -p.lag)
    return LagResult(group=group, total_lag=total,
                     partitions=parts_sorted, findings=findings)
