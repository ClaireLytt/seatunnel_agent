"""Deterministic capacity exhaustion forecast over storage series.

Input is the same ``date,metric,value`` series the data_volatility
agent reads (parser reused): one metric per table (value = size in GB,
or rows), several tables in one paste.  Per metric, the daily growth
comes from a least-squares slope over the most recent window (dates
used as real day offsets when ISO, row order otherwise).  The total —
a metric literally named ``total`` when present, otherwise the sum of
the latest values with the summed slope — is projected against the
quota: days left and the exhaustion date.  Findings: CF001 quota
exhaustion inside the horizon (30 days high / 90 mid), CF002 the top
growers carrying the trend, CF003 shrinking metrics (reclaim working).
Linear extrapolation is stated, not hidden.  No storage connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from seatunnel_agent.agents.data.data_volatility import parse_series

__all__ = ["CapacityResult", "CfFinding", "MetricTrend",
           "forecast_capacity"]

_WINDOW = 14
_HORIZON_DAYS = (90.0, 30.0)     # mid, high (inverted: fewer days worse)
_TOP_GROWERS = 5


@dataclass
class MetricTrend:
    metric: str
    latest: float
    daily_growth: float
    points: int

    def to_dict(self) -> dict:
        return {"metric": self.metric, "latest": round(self.latest, 2),
                "daily_growth": round(self.daily_growth, 3),
                "points": self.points}


@dataclass
class CfFinding:
    code: str          # CF001..
    severity: str      # high / mid / low
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail}


@dataclass
class CapacityResult:
    quota: float
    total_latest: float
    total_daily_growth: float
    days_left: float | None
    exhaustion_date: str
    trends: list[MetricTrend]
    findings: list[CfFinding]

    def to_dict(self) -> dict:
        return {"quota": self.quota,
                "total_latest": round(self.total_latest, 2),
                "total_daily_growth": round(self.total_daily_growth, 3),
                "days_left": (round(self.days_left, 1)
                              if self.days_left is not None else None),
                "exhaustion_date": self.exhaustion_date,
                "trends": [t.to_dict() for t in self.trends],
                "findings": [f.to_dict() for f in self.findings]}


def _day_offsets(dates: list[str]) -> list[float]:
    try:
        parsed = [date.fromisoformat(d) for d in dates]
        base = parsed[0]
        return [float((d - base).days) for d in parsed]
    except ValueError:
        return [float(i) for i in range(len(dates))]


def _slope(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom


def forecast_capacity(series_text: str, quota: float,
                      window: int = _WINDOW,
                      today: date | None = None) -> CapacityResult:
    if quota <= 0:
        raise ValueError("quota must be > 0 / 配额须大于 0")
    series = parse_series(series_text)
    today = today or date.today()

    trends: list[MetricTrend] = []
    for metric, pts in sorted(series.items()):
        recent = pts[-window:]
        xs = _day_offsets([d for d, _ in recent])
        ys = [v for _, v in recent]
        trends.append(MetricTrend(metric=metric, latest=ys[-1],
                                  daily_growth=_slope(xs, ys),
                                  points=len(pts)))

    named_total = next((t for t in trends if t.metric == "total"), None)
    if named_total is not None:
        total_latest = named_total.latest
        total_growth = named_total.daily_growth
    else:
        total_latest = sum(t.latest for t in trends)
        total_growth = sum(t.daily_growth for t in trends)

    days_left: float | None = None
    exhaustion = "-"
    if total_growth > 0 and total_latest < quota:
        days_left = (quota - total_latest) / total_growth
        exhaustion = (today + timedelta(days=int(days_left))).isoformat()
    elif total_latest >= quota:
        days_left = 0.0
        exhaustion = today.isoformat()

    findings: list[CfFinding] = []
    if days_left is not None:
        mid_h, high_h = _HORIZON_DAYS
        sev = ("high" if days_left <= high_h
               else "mid" if days_left <= mid_h else None)
        if sev:
            findings.append(CfFinding("CF001", sev, {
                "days_left": round(days_left, 1),
                "exhaustion_date": exhaustion, "quota": quota,
                "total_latest": round(total_latest, 2),
                "daily_growth": round(total_growth, 3)}))

    growers = sorted((t for t in trends
                      if t.daily_growth > 0 and t.metric != "total"),
                     key=lambda t: -t.daily_growth)[:_TOP_GROWERS]
    if growers and total_growth > 0:
        findings.append(CfFinding("CF002", "mid", {
            "top": [{"metric": g.metric,
                     "daily_growth": round(g.daily_growth, 3),
                     "share_pct": round(100 * g.daily_growth
                                        / total_growth, 1)}
                    for g in growers]}))

    shrinking = sorted((t for t in trends
                        if t.daily_growth < 0 and t.metric != "total"),
                       key=lambda t: t.daily_growth)
    if shrinking:
        findings.append(CfFinding("CF003", "low", {
            "metrics": [{"metric": s.metric,
                         "daily_growth": round(s.daily_growth, 3)}
                        for s in shrinking[:5]]}))

    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code))
    trends.sort(key=lambda t: -t.daily_growth)
    return CapacityResult(quota=quota, total_latest=total_latest,
                          total_daily_growth=total_growth,
                          days_left=days_left,
                          exhaustion_date=exhaustion, trends=trends,
                          findings=findings)
