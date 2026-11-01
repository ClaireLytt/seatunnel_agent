"""Deterministic volatility analysis over metric time series.

Input is CSV (``date,metric,value`` header) or JSONL rows with the same
fields; several metrics may share one file.  Per metric, sorted by date,
the analyzer flags point spikes and dips against a rolling median + MAD
window, level shifts (recent median vs prior median), flatlines where a
previously moving series froze, and date gaps.  Every finding carries
the evidence numbers; thresholds are fixed and documented in the report
footer.  No database connection.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import date, timedelta

__all__ = ["VolFinding", "VolResult", "analyze_series", "parse_series"]

_WINDOW = 7          # rolling window of prior points
_MAD_K = 5.0         # spike: |v - med| > K * MAD
_REL_SPIKE = (0.5, 1.0)     # surge grading (mid, high), relative
_REL_DROP = (0.3, 0.6)      # drop grading — a drop tops out at -100%
_SHIFT = (0.3, 0.6)         # level shift of recent vs prior median
_RECENT = 3          # points in the "recent" slice


@dataclass
class VolFinding:
    code: str          # VA001..
    severity: str      # high / mid / low
    metric: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"code": self.code, "severity": self.severity,
                "metric": self.metric, "detail": self.detail}


@dataclass
class VolResult:
    metrics: dict[str, int]          # metric -> points
    findings: list[VolFinding]

    def to_dict(self) -> dict:
        return {"metrics": self.metrics,
                "findings": [f.to_dict() for f in self.findings]}


def parse_series(text: str) -> dict[str, list[tuple[str, float]]]:
    """CSV/JSONL rows → {metric: [(date, value)] sorted by date}."""
    body = (text or "").strip()
    if not body:
        raise ValueError("empty input / 输入为空")
    rows: list[dict] = []
    if body.lstrip()[:1] in "{[":
        items = (json.loads(body) if body.lstrip().startswith("[")
                 else [json.loads(ln) for ln in body.splitlines()
                       if ln.strip()])
        rows = list(items)
    else:
        reader = csv.DictReader(io.StringIO(body))
        rows = [dict(r) for r in reader]
    series: dict[str, list[tuple[str, float]]] = {}
    for i, row in enumerate(rows, start=1):
        low = {str(k).strip().lower(): v for k, v in row.items()
               if k is not None}
        d, m, v = low.get("date"), low.get("metric"), low.get("value")
        if d is None or v in (None, ""):
            raise ValueError(f"row {i}: needs date/metric/value / "
                             f"第 {i} 行缺 date/metric/value")
        try:
            val = float(v)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"row {i}: value '{v}' is not a number") from exc
        series.setdefault(str(m or "value"), []).append((str(d).strip(), val))
    for pts in series.values():
        pts.sort(key=lambda p: p[0])
    return series


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _grade(rel: float, thresholds: tuple[float, float]) -> str | None:
    mid, high = thresholds
    if rel >= high:
        return "high"
    if rel >= mid:
        return "mid"
    return None


def analyze_series(series: dict[str, list[tuple[str, float]]],
                   period: int = 7) -> VolResult:
    findings: list[VolFinding] = []
    for metric, pts in sorted(series.items()):
        findings.extend(_analyze_metric(metric, pts, period=period))
    order = {"high": 0, "mid": 1, "low": 2}
    findings.sort(key=lambda f: (order[f.severity], f.code, f.metric))
    return VolResult(metrics={m: len(p) for m, p in sorted(series.items())},
                     findings=findings)


def _analyze_metric(metric: str, pts: list[tuple[str, float]],
                    period: int = 7) -> list[VolFinding]:
    out: list[VolFinding] = []
    values = [v for _, v in pts]
    # VA001/VA002 point spikes and dips against the rolling window;
    # a run of flagged points in one direction reports only its first
    # point — the persisting level is VA003's job
    last_code: str | None = None
    for i in range(1, len(pts)):
        window = values[max(0, i - _WINDOW):i]
        if len(window) < 3:
            continue
        med = _median(window)
        mad = _median([abs(x - med) for x in window])
        v = values[i]
        rel = abs(v - med) / max(abs(med), 1e-9)
        robust = mad > 0 and abs(v - med) > _MAD_K * mad
        code = "VA001" if v > med else "VA002"
        sev = _grade(rel, _REL_SPIKE if code == "VA001" else _REL_DROP)
        if sev and (robust or mad == 0):
            if code != last_code:
                out.append(VolFinding(code, sev, metric, {
                    "date": pts[i][0], "value": v, "window_median": med,
                    "change_pct": round(
                        100 * (v - med) / max(abs(med), 1e-9), 1)}))
            last_code = code
        else:
            last_code = None
    # VA003 level shift: recent median vs the median before it
    if len(values) >= _RECENT + 3:
        recent = _median(values[-_RECENT:])
        prior = _median(values[:-_RECENT])
        rel = abs(recent - prior) / max(abs(prior), 1e-9)
        sev = _grade(rel, _SHIFT)
        # a shift carried by a single spike is already reported above
        spike_dates = {f.detail["date"] for f in out}
        recent_dates = {d for d, _ in pts[-_RECENT:]}
        if sev and not recent_dates <= spike_dates:
            out.append(VolFinding("VA003", sev, metric, {
                "from": prior, "to": recent,
                "shift_pct": round(100 * (recent - prior)
                                   / max(abs(prior), 1e-9), 1)}))
    # VA004 flatline: the last window froze while history moved
    if len(values) >= 2 * _RECENT:
        tail = values[-_RECENT:]
        head = values[:-_RECENT]
        if len(set(tail)) == 1 and len(set(head)) > 1:
            out.append(VolFinding("VA004", "mid", metric, {
                "value": tail[0], "points": _RECENT,
                "since": pts[-_RECENT][0]}))
    # VA006 环比 / VA007 同比 on the latest point; a point already
    # reported as a spike is not re-reported
    spike_dates = {f.detail.get("date") for f in out
                   if f.code in ("VA001", "VA002")}
    if pts and pts[-1][0] not in spike_dates:
        last_date, last = pts[-1]
        if len(values) >= 2 and values[-2] != 0:
            rel = (last - values[-2]) / abs(values[-2])
            sev = _grade(abs(rel), _SHIFT)
            if sev:
                out.append(VolFinding("VA006", sev, metric, {
                    "date": last_date, "value": last, "prev": values[-2],
                    "change_pct": round(100 * rel, 1)}))
        if len(values) > period and values[-1 - period] != 0:
            base = values[-1 - period]
            rel = (last - base) / abs(base)
            sev = _grade(abs(rel), _SHIFT)
            if sev:
                out.append(VolFinding("VA007", sev, metric, {
                    "date": last_date, "value": last, "base": base,
                    "period": period,
                    "change_pct": round(100 * rel, 1)}))

    # VA005 date gaps (ISO dates only; other labels are skipped quietly)
    gaps = _date_gaps([d for d, _ in pts])
    if gaps:
        out.append(VolFinding("VA005", "low", metric, {"gaps": gaps[:5]}))
    return out


def _date_gaps(dates: list[str]) -> list[str]:
    parsed: list[date] = []
    for d in dates:
        try:
            parsed.append(date.fromisoformat(d))
        except ValueError:
            return []
    gaps = []
    for a, b in zip(parsed, parsed[1:]):
        if (b - a).days > 1:
            missing = (b - a).days - 1
            first = a + timedelta(days=1)
            gaps.append(f"{first.isoformat()} (+{missing})")
    return gaps
