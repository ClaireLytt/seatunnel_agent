"""Deterministic dimensional attribution of a metric change.

Input is two result sets sliced by dimensions — baseline (yesterday /
last week) and current — as CSV with a header or JSONL (the
sample_profile parser is reused), plus the dimension column(s) and the
metric column.  The headline is the total change; per dimension the
change decomposes exactly into per-value contributions
(current - baseline, with appeared and vanished values included), so
"GMV dropped 10% — which channel did it" gets a ranked, additive
answer.  Findings: MA001 the top contributor per dimension, MA002
concentration (one value carrying most of the move), MA003 offsetting
moves (ups and downs largely cancelling — a mix shift the total
hides).  No database connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from seatunnel_agent.agents.data.sample_profile import parse_rows

__all__ = ["AttributionResult", "DimBreakdown", "MaFinding",
           "attribute_change"]

_CONCENTRATION = 0.5
_OFFSET_RATIO = 1.5      # |ups| + |downs| vs |net| -> mix shift
_TOP_VALUES = 6


@dataclass
class DimBreakdown:
    dimension: str
    movers: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"dimension": self.dimension, "movers": self.movers}


@dataclass
class MaFinding:
    code: str          # MA001..
    severity: str      # high / mid / low
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "detail": self.detail}


@dataclass
class AttributionResult:
    metric: str
    total_base: float
    total_cur: float
    delta: float
    delta_pct: float | None
    breakdowns: list[DimBreakdown]
    findings: list[MaFinding]

    def to_dict(self) -> dict:
        return {"metric": self.metric,
                "total_base": round(self.total_base, 2),
                "total_cur": round(self.total_cur, 2),
                "delta": round(self.delta, 2),
                "delta_pct": self.delta_pct,
                "breakdowns": [b.to_dict() for b in self.breakdowns],
                "findings": [f.to_dict() for f in self.findings]}


def _num(value) -> float:
    if value in (None, ""):
        return 0.0
    return float(str(value).replace(",", ""))


def _sums(headers: list[str], rows: list[dict], dim: str,
          metric: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for r in rows:
        key = str(r.get(dim)) if r.get(dim) is not None else "∅"
        out[key] = out.get(key, 0.0) + _num(r.get(metric))
    return out


def attribute_change(baseline_text: str, current_text: str, dims: str,
                     metric: str) -> AttributionResult:
    dim_cols = [d.strip() for d in (dims or "").split(",") if d.strip()]
    metric = (metric or "").strip()
    if not dim_cols:
        raise ValueError("dimension column(s) required / 需要维度列")
    if not metric:
        raise ValueError("metric column required / 需要指标列")
    b_headers, b_rows = parse_rows(baseline_text)
    c_headers, c_rows = parse_rows(current_text)
    for col in [*dim_cols, metric]:
        if col not in b_headers or col not in c_headers:
            raise ValueError(f"column '{col}' missing on one side / "
                             f"列不存在于某一侧")

    total_base = sum(_num(r.get(metric)) for r in b_rows)
    total_cur = sum(_num(r.get(metric)) for r in c_rows)
    delta = total_cur - total_base
    delta_pct = (round(100 * delta / abs(total_base), 2)
                 if total_base else None)

    breakdowns: list[DimBreakdown] = []
    findings: list[MaFinding] = []
    for dim in dim_cols:
        base = _sums(b_headers, b_rows, dim, metric)
        cur = _sums(c_headers, c_rows, dim, metric)
        movers = []
        for value in sorted(set(base) | set(cur)):
            b_v, c_v = base.get(value, 0.0), cur.get(value, 0.0)
            contrib = c_v - b_v
            if contrib == 0:
                continue
            movers.append({
                "value": value, "baseline": round(b_v, 2),
                "current": round(c_v, 2),
                "contribution": round(contrib, 2),
                "share_pct": (round(100 * contrib / abs(delta), 1)
                              if delta else None),
                "status": ("appeared" if value not in base
                           else "vanished" if value not in cur
                           else "moved")})
        movers.sort(key=lambda m: -abs(m["contribution"]))
        breakdowns.append(DimBreakdown(dimension=dim,
                                       movers=movers[:_TOP_VALUES * 2]))
        if not movers:
            continue

        top = movers[0]
        if delta != 0:
            share = abs(top["contribution"]) / abs(delta)
            findings.append(MaFinding("MA001", "high", {
                "dimension": dim, "value": top["value"],
                "contribution": top["contribution"],
                "share_pct": round(100 * share, 1),
                "direction": "drop" if delta < 0 else "rise"}))
            if share >= _CONCENTRATION:
                findings.append(MaFinding("MA002", "high", {
                    "dimension": dim, "value": top["value"],
                    "share_pct": round(100 * share, 1)}))
        ups = sum(m["contribution"] for m in movers
                  if m["contribution"] > 0)
        downs = -sum(m["contribution"] for m in movers
                     if m["contribution"] < 0)
        gross = ups + downs
        if gross and abs(delta) < gross / _OFFSET_RATIO:
            findings.append(MaFinding("MA003", "mid", {
                "dimension": dim, "ups": round(ups, 2),
                "downs": round(downs, 2), "net": round(delta, 2)}))

    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code,
                                 str(f.detail.get("dimension"))))
    return AttributionResult(metric=metric, total_base=total_base,
                             total_cur=total_cur, delta=delta,
                             delta_pct=delta_pct, breakdowns=breakdowns,
                             findings=findings)
