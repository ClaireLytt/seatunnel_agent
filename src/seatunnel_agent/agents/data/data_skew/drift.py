"""Skew drift detection over the splitkey patrol history.

Each ``skew-splitkey`` run already logs the configured key's measured
metrics (top1_pct / ndv / null_pct) into ``logs/data_skew.jsonl``
(history.log_splitkey).  This module reads that per-table trend and says
whether the *latest* measurement drifted from its baseline — the median
of the earlier measurements — so a column that slowly grows a hot key is
flagged before it becomes a sync incident.

Pure functions over history records; no live SQL, no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

# Latest-vs-baseline thresholds (percentage points / percent).
TOP1_DRIFT_PP = 10.0     # top-1 concentration rose by >= 10 pp
NULL_DRIFT_PP = 5.0      # NULL share rose by >= 5 pp
NDV_DROP_PCT = 30.0      # distinct count fell by >= 30 %

MIN_HISTORY = 3          # need baseline(>=2) + latest to call a drift


@dataclass
class MetricDrift:
    """One drifted metric of one measured split key."""

    metric: str            # top1_pct | null_pct | ndv
    baseline: float
    current: float
    delta: float           # current - baseline (pp for pcts, % drop for ndv)


@dataclass
class DriftResult:
    """Drift verdict for one table's splitkey trend."""

    table: str
    column: str = ""
    verdict: str = "insufficient"   # drift | stable | insufficient
    samples: int = 0
    drifts: list[MetricDrift] = field(default_factory=list)


def _metric_series(records: list[dict], key: str) -> list[float]:
    vals: list[float] = []
    for rec in records:
        sk = rec.get("splitkey") or {}
        v = sk.get(key)
        if isinstance(v, (int, float)):
            vals.append(float(v))
    return vals


def compute_drift(table: str, records: list[dict]) -> DriftResult:
    """Drift verdict from splitkey history *records* (oldest first).

    Records are the dicts ``SkewHistory.splitkey_trend`` returns.  Only
    records carrying measured metrics count; with fewer than
    ``MIN_HISTORY`` of them the verdict is ``insufficient``.
    """
    measured = [r for r in records
                if any(k in (r.get("splitkey") or {})
                       for k in ("top1_pct", "null_pct", "ndv"))]
    result = DriftResult(table=table, samples=len(measured))
    if measured:
        result.column = str(
            (measured[-1].get("splitkey") or {}).get("partition_column") or "")
    if len(measured) < MIN_HISTORY:
        return result

    baseline_recs, latest = measured[:-1], measured[-1:]

    def check(key: str, threshold: float, *, drop: bool = False) -> None:
        base_vals = _metric_series(baseline_recs, key)
        cur_vals = _metric_series(latest, key)
        if not base_vals or not cur_vals:
            return
        base, cur = median(base_vals), cur_vals[0]
        if drop:
            if base <= 0:
                return
            delta = (base - cur) / base * 100.0
            if delta >= threshold:
                result.drifts.append(MetricDrift(key, base, cur, round(-delta, 2)))
        else:
            delta = cur - base
            if delta >= threshold:
                result.drifts.append(MetricDrift(key, base, cur, round(delta, 2)))

    check("top1_pct", TOP1_DRIFT_PP)
    check("null_pct", NULL_DRIFT_PP)
    check("ndv", NDV_DROP_PCT, drop=True)

    result.verdict = "drift" if result.drifts else "stable"
    return result


def render_drift(result: DriftResult, lang: str = "zh") -> str:
    """One shared textual rendering for CLI / splitkey tail / webhook."""
    from .i18n import dsk

    if result.verdict == "insufficient":
        return dsk(lang, "drf_insufficient").format(
            table=result.table, n=result.samples)
    key = "drf_drift" if result.verdict == "drift" else "drf_stable"
    lines = [dsk(lang, key).format(
        table=result.table, col=result.column or "(none)", n=result.samples)]
    for d in result.drifts:
        lines.append(dsk(lang, "drf_metric").format(
            metric=d.metric, base=d.baseline, cur=d.current, delta=d.delta))
    return "\n".join(lines)
