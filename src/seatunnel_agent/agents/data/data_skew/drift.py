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
    # hot-value identity: did the top-1 value itself change vs the baseline?
    top1_value_prev: str = ""
    top1_value_cur: str = ""

    @property
    def hot_value_changed(self) -> bool:
        return bool(self.top1_value_prev and self.top1_value_cur
                    and self.top1_value_prev != self.top1_value_cur)


def _metric_series(records: list[dict], key: str) -> list[float]:
    vals: list[float] = []
    for rec in records:
        sk = rec.get("splitkey") or {}
        v = sk.get(key)
        if isinstance(v, (int, float)):
            vals.append(float(v))
    return vals


def compute_drift(table: str, records: list[dict],
                  column: str = "") -> DriftResult:
    """Drift verdict from splitkey history *records* (oldest first).

    Records are the dicts ``SkewHistory.splitkey_trend`` returns.  Only
    records carrying measured metrics count; with fewer than
    ``MIN_HISTORY`` of them the verdict is ``insufficient``.

    A table's history may hold measurements of different keys (e.g. the
    key was changed, or two configs read the same table), so the series
    is one *column*: the given one, or the latest measured record's.
    """
    measured = [r for r in records
                if any(k in (r.get("splitkey") or {})
                       for k in ("top1_pct", "null_pct", "ndv"))]
    if not column and measured:
        column = str(
            (measured[-1].get("splitkey") or {}).get("partition_column") or "")
    measured = [r for r in measured
                if str((r.get("splitkey") or {}).get("partition_column") or "")
                == column]
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

    # hot-value identity: latest vs the most recent earlier measurement
    # that recorded one (older records may predate top1_value logging)
    def _top1_value(rec: dict) -> str:
        return str((rec.get("splitkey") or {}).get("top1_value") or "")

    result.top1_value_cur = _top1_value(latest[0])
    for rec in reversed(baseline_recs):
        if _top1_value(rec):
            result.top1_value_prev = _top1_value(rec)
            break

    result.verdict = "drift" if result.drifts else "stable"
    return result


def notify_decision(prev: dict | None, result: DriftResult) -> tuple[bool, str]:
    """Should this patrol's outcome be alerted, given the previous drift
    record (``SkewHistory.last_drift``, read BEFORE logging this run)?

    Returns ``(notify, kind)`` with kind one of ``"drift"`` (first report),
    ``"worse"`` (escalation: a new drifted metric, or a shared metric whose
    delta grew), ``"recovered"`` (back to stable after a reported drift),
    or ``""`` (stay silent: unchanged drift, steady stable, insufficient).
    """
    prev_d = (prev.get("drift") or {}) if prev else {}
    prev_verdict = str(prev_d.get("drift_verdict") or "")
    prev_deltas = {k: float(v) for k, v in (prev_d.get("deltas") or {}).items()}
    if result.verdict == "drift":
        if prev_verdict != "drift":
            return True, "drift"
        worse = any(
            d.metric not in prev_deltas
            or abs(d.delta) > abs(prev_deltas[d.metric])
            for d in result.drifts
        )
        return (worse, "worse" if worse else "")
    if result.verdict == "stable" and prev_verdict == "drift":
        return True, "recovered"
    return False, ""


def drift_item_dict(result: DriftResult, lang: str = "zh") -> dict:
    """One serialized drift item — the single shape the REST endpoint and
    the CLI's JSON format share."""
    return {
        "table": result.table,
        "column": result.column,
        "verdict": result.verdict,
        "samples": result.samples,
        "drifts": [{"metric": d.metric, "baseline": d.baseline,
                    "current": d.current, "delta": d.delta}
                   for d in result.drifts],
        "hot_value": {"prev": result.top1_value_prev,
                      "cur": result.top1_value_cur,
                      "changed": result.hot_value_changed},
        "text": render_drift(result, lang),
    }


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
    if result.verdict == "drift" and result.hot_value_changed:
        lines.append(dsk(lang, "drf_hot_changed").format(
            prev=result.top1_value_prev, cur=result.top1_value_cur))
    return "\n".join(lines)
