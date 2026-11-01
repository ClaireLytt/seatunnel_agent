"""Deterministic alert-storm clustering and noise reduction.

Input is an alert export — CSV with a header or a JSON list::

    [{"ts": "2026-10-31 02:11:04", "source": "dqc",
      "title": "null_rate over 5% on dwd.orders dt=2026-10-30",
      "level": "warn"}]

Alerts cluster by a normalized title signature (digits, dates and paths
stripped — the same trick the task_failure agent uses), so one root
cause is one row however many pages it sent.  On top of the clusters:
AS002 storm windows (5-minute buckets far above the median bucket),
AS003 flapping signatures (the same alert firing again and again inside
an hour — the suppression-window candidates), and AS004 a noisy source
carrying most of the channel.  The headline number is the dedup ratio:
how many pages the channel sent vs how many distinct things actually
happened.  No alerting-system connection.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime

__all__ = ["Alert", "AlertCluster", "AsFinding", "StormResult",
           "analyze_alerts", "parse_alerts"]

_SIG_NOISE = re.compile(r"[\d/:\\.\-_=']+")
_BUCKET_S = 300                 # 5-minute storm buckets
_STORM_RATIO = 3.0              # bucket vs median bucket
_FLAP_COUNT = 5                 # same signature, inside one hour
_FLAP_WINDOW_S = 3600
_NOISY_SHARE = 0.5


@dataclass
class Alert:
    ts: datetime | None
    source: str
    title: str
    level: str

    def to_dict(self) -> dict:
        return {"ts": self.ts.isoformat() if self.ts else None,
                "source": self.source, "title": self.title[:120],
                "level": self.level}


@dataclass
class AlertCluster:
    signature: str
    count: int
    sources: list[str]
    levels: list[str]
    sample_title: str
    first_ts: str
    last_ts: str

    def to_dict(self) -> dict:
        return {"signature": self.signature, "count": self.count,
                "sources": self.sources, "levels": self.levels,
                "sample_title": self.sample_title[:120],
                "first_ts": self.first_ts, "last_ts": self.last_ts}


@dataclass
class AsFinding:
    code: str          # AS002..
    severity: str      # high / mid / low
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail}


@dataclass
class StormResult:
    total: int
    clusters: list[AlertCluster]
    findings: list[AsFinding]

    @property
    def dedup_ratio(self) -> float:
        return (self.total / len(self.clusters)) if self.clusters else 0.0

    def to_dict(self) -> dict:
        return {"total": self.total,
                "distinct": len(self.clusters),
                "dedup_ratio": round(self.dedup_ratio, 1),
                "clusters": [c.to_dict() for c in self.clusters[:12]],
                "findings": [f.to_dict() for f in self.findings]}


def _ts(value) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).strip())
    except ValueError:
        return None


def parse_alerts(text: str) -> list[Alert]:
    body = (text or "").strip()
    if not body:
        raise ValueError("empty export / 导出为空")
    if body.startswith("["):
        items = json.loads(body)
    else:
        items = [dict(r) for r in csv.DictReader(io.StringIO(body))]
    alerts: list[Alert] = []
    for i, it in enumerate(items, start=1):
        if not isinstance(it, dict) or not (it.get("title") or "").strip():
            raise ValueError(f"row {i}: needs 'title' / 第 {i} 行缺 title")
        alerts.append(Alert(
            ts=_ts(it.get("ts")),
            source=str(it.get("source") or "?").strip(),
            title=str(it["title"]).strip(),
            level=str(it.get("level") or "warn").strip().lower()))
    if not alerts:
        raise ValueError("no alerts / 没有告警")
    return alerts


def _signature(title: str) -> str:
    sig = _SIG_NOISE.sub(" ", title.lower())
    return " ".join(sig.split())[:70]


def analyze_alerts(alerts: list[Alert]) -> StormResult:
    groups: dict[str, list[Alert]] = {}
    for a in alerts:
        groups.setdefault(_signature(a.title), []).append(a)

    clusters: list[AlertCluster] = []
    for sig, members in groups.items():
        stamped = sorted((m for m in members if m.ts),
                         key=lambda m: m.ts)
        clusters.append(AlertCluster(
            signature=sig, count=len(members),
            sources=sorted({m.source for m in members}),
            levels=sorted({m.level for m in members}),
            sample_title=members[0].title,
            first_ts=stamped[0].ts.isoformat() if stamped else "-",
            last_ts=stamped[-1].ts.isoformat() if stamped else "-"))
    clusters.sort(key=lambda c: (-c.count, c.signature))

    findings: list[AsFinding] = []

    # AS002 storm windows: 5-minute buckets vs the median bucket
    stamped = sorted((a for a in alerts if a.ts), key=lambda a: a.ts)
    if len(stamped) >= 8:
        buckets: dict[int, int] = {}
        for a in stamped:
            buckets[int(a.ts.timestamp()) // _BUCKET_S] = \
                buckets.get(int(a.ts.timestamp()) // _BUCKET_S, 0) + 1
        counts = sorted(buckets.values())
        med = counts[len(counts) // 2]
        storms = [(b, n) for b, n in sorted(buckets.items())
                  if med > 0 and n >= _STORM_RATIO * med and n >= 5]
        if storms:
            worst_b, worst_n = max(storms, key=lambda x: x[1])
            findings.append(AsFinding("AS002", "high", {
                "windows": len(storms),
                "worst_start": datetime.fromtimestamp(
                    worst_b * _BUCKET_S).isoformat(),
                "worst_count": worst_n, "median_per_bucket": med}))

    # AS003 flapping: one signature >= N firings inside an hour
    for c in clusters:
        members = sorted((m for m in groups[c.signature] if m.ts),
                         key=lambda m: m.ts)
        if len(members) < _FLAP_COUNT:
            continue
        for i in range(len(members) - _FLAP_COUNT + 1):
            span = (members[i + _FLAP_COUNT - 1].ts
                    - members[i].ts).total_seconds()
            if span <= _FLAP_WINDOW_S:
                findings.append(AsFinding("AS003", "mid", {
                    "signature": c.signature,
                    "firings": c.count,
                    "window_min": round(span / 60, 1)}))
                break

    # AS004 noisy source
    by_source: dict[str, int] = {}
    for a in alerts:
        by_source[a.source] = by_source.get(a.source, 0) + 1
    top_source, top_n = max(by_source.items(), key=lambda kv: kv[1])
    if len(by_source) > 1 and top_n / len(alerts) >= _NOISY_SHARE:
        findings.append(AsFinding("AS004", "mid", {
            "source": top_source, "count": top_n,
            "share_pct": round(100 * top_n / len(alerts), 1)}))

    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code,
                                 str(f.detail.get("signature", ""))))
    return StormResult(total=len(alerts), clusters=clusters,
                       findings=findings)
