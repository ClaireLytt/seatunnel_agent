"""Trend alerting over compare-report history (F4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Trend alerting  (F4)
# ---------------------------------------------------------------------------


@dataclass
class AlertRule:
    """Parsed alert rule from user input."""
    metric: str
    threshold: float
    consecutive: int


@dataclass
class TrendAlert:
    """A single alert rule evaluation result."""
    metric: str
    threshold: float
    consecutive_required: int
    consecutive_actual: int
    triggered: bool
    current_value: float | None = None


def parse_alert_rules(raw: str) -> list[AlertRule]:
    """Parse alert rules from a string like ``row_count_delta>100:3, mismatches>0:5``.

    Each rule: ``metric>threshold:consecutive_count``
    """
    rules: list[AlertRule] = []
    for line in raw.replace(",", "\n").strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            left, consecutive_str = line.rsplit(":", 1)
            consecutive = int(consecutive_str)
            if ">" in left:
                metric, threshold_str = left.split(">", 1)
                rules.append(AlertRule(
                    metric=metric.strip(),
                    threshold=float(threshold_str),
                    consecutive=max(1, consecutive),
                ))
        except (ValueError, IndexError):
            continue
    return rules


def check_trend_alerts(
    trend_data: list[dict[str, Any]],
    alert_rules: list[AlertRule],
) -> list[TrendAlert]:
    """Check trend data against alert rules.

    *trend_data* is the output of ``build_trend_data()``.
    """
    _metric_extractors: dict[str, str] = {
        "row_count_delta": "delta",
        "delta": "delta",
        "delta_pct": "delta_pct",
        "mismatches": "mismatches",
    }

    results: list[TrendAlert] = []
    for rule in alert_rules:
        metric = rule.metric
        threshold = rule.threshold
        required = rule.consecutive
        field = _metric_extractors.get(metric, metric)

        consecutive = 0
        current_val: float | None = None
        for entry in reversed(trend_data):
            val = entry.get(field)
            if val is None:
                break
            current_val = current_val if current_val is not None else float(val)
            if abs(float(val)) > threshold:
                consecutive += 1
            else:
                break

        results.append(TrendAlert(
            metric=metric,
            threshold=threshold,
            consecutive_required=required,
            consecutive_actual=consecutive,
            triggered=consecutive >= required,
            current_value=current_val,
        ))
    return results


