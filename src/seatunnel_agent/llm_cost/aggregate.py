# -*- coding: utf-8 -*-
"""Cost aggregation over the cross-agent LLM usage log.

Reads the same JSONL that :mod:`seatunnel_agent.llm_usage` appends to
(``{ts, provider, model, input, output}``, plus an optional ``agent`` field),
prices every call via :mod:`.pricing`, and rolls the result up per model /
day / agent.  Deterministic — no DB, no LLM.

Anomaly rule: a (UTC) day is flagged when its cost exceeds
``ANOMALY_FACTOR ×`` the mean of the trailing 7 days, and at least
``ANOMALY_MIN_HISTORY`` of those days actually have spend — a brand-new log
never alarms.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..llm_usage import usage_path
from .pricing import PriceEntry, cost_usd, merged_prices

ANOMALY_FACTOR = 2.0
ANOMALY_MIN_HISTORY = 3
_TRAILING_DAYS = 7


def _new_bucket() -> dict[str, Any]:
    return {"calls": 0, "input": 0, "output": 0, "cost_usd": 0.0,
            "unpriced_calls": 0}


def summarize_cost(days: int = 30,
                   usage_file: str | Path | None = None,
                   prices: list[PriceEntry] | None = None,
                   pricing_override: str | Path | None = None,
                   ) -> dict[str, Any]:
    """Cost/usage summary for the last *days* days (UTC).

    Returns a JSON-serializable dict::

        {days, total: {calls, input, output, cost_usd, unpriced_calls},
         by_model: {model: bucket}, by_agent: {agent: bucket},
         by_day: {date: bucket}, by_day_model: {date: {model: cost_usd}},
         unpriced_models: [...], anomalies: [{day, cost_usd, baseline_usd}]}

    Unpriced calls still count tokens; their cost contribution is 0 and the
    models are listed so the report can say which spend is missing.
    """
    if prices is None:
        prices = merged_prices(pricing_override)
    path = Path(usage_file) if usage_file else usage_path()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    total = _new_bucket()
    by_model: dict[str, dict[str, Any]] = defaultdict(_new_bucket)
    by_agent: dict[str, dict[str, Any]] = defaultdict(_new_bucket)
    by_day: dict[str, dict[str, Any]] = defaultdict(_new_bucket)
    by_day_model: dict[str, dict[str, float]] = defaultdict(
        lambda: defaultdict(float))
    unpriced: set[str] = set()

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    for line in text.splitlines():
        try:
            rec = json.loads(line)
            ts = datetime.strptime(rec["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
            inp = int(rec.get("input", 0) or 0)
            out = int(rec.get("output", 0) or 0)
        except (ValueError, KeyError, TypeError):
            continue  # one malformed line must not kill the whole summary
        if ts < cutoff:
            continue
        model = str(rec.get("model", "?"))
        agent = str(rec.get("agent") or "unattributed")
        day = ts.strftime("%Y-%m-%d")
        cost = cost_usd(model, inp, out, prices)
        if cost is None:
            unpriced.add(model)
        for bucket in (total, by_model[model], by_agent[agent], by_day[day]):
            bucket["calls"] += 1
            bucket["input"] += inp
            bucket["output"] += out
            if cost is None:
                bucket["unpriced_calls"] += 1
            else:
                bucket["cost_usd"] += cost
        if cost is not None:
            by_day_model[day][model] += cost

    for buckets in (total, *by_model.values(), *by_agent.values(),
                    *by_day.values()):
        buckets["cost_usd"] = round(buckets["cost_usd"], 6)

    return {
        "days": days,
        "total": total,
        "by_model": dict(by_model),
        "by_agent": dict(by_agent),
        "by_day": dict(by_day),
        "by_day_model": {d: dict(m) for d, m in by_day_model.items()},
        "unpriced_models": sorted(unpriced),
        "anomalies": _find_anomalies(
            {d: b["cost_usd"] for d, b in by_day.items()}),
    }


def _find_anomalies(cost_by_day: dict[str, float]) -> list[dict[str, Any]]:
    """Days whose cost spikes above the trailing-window mean."""
    anomalies: list[dict[str, Any]] = []
    for day in sorted(cost_by_day):
        d = datetime.strptime(day, "%Y-%m-%d")
        window = []
        for back in range(1, _TRAILING_DAYS + 1):
            prev = (d - timedelta(days=back)).strftime("%Y-%m-%d")
            if prev in cost_by_day and cost_by_day[prev] > 0:
                window.append(cost_by_day[prev])
        if len(window) < ANOMALY_MIN_HISTORY:
            continue
        baseline = sum(window) / len(window)
        if baseline > 0 and cost_by_day[day] > ANOMALY_FACTOR * baseline:
            anomalies.append({
                "day": day,
                "cost_usd": round(cost_by_day[day], 6),
                "baseline_usd": round(baseline, 6),
            })
    return anomalies


def check_budget(summary: dict[str, Any], budget_usd: float) -> bool:
    """True when the period's priced spend exceeds the budget."""
    return float(summary["total"]["cost_usd"]) > budget_usd
