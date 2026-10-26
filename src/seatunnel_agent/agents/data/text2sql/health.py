"""Per-metric health rollup — the data team's one-command ops view.

Joins four signals that already exist elsewhere: table freshness
(``_max_time_value``), 7-day query stats from qlog, the subscriptions
feeding on the metric (and whether any is currently alerting), and
month-target completion. Deterministic and LLM-free; every signal is
best-effort so one broken metric never hides the others.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from .metrics import MetricStore, build_metric_sql
from .partition import TimeRange
from .schema import SchemaStore
from .validator import enforce_limit, validate_sql


def _qlog_7d(entries: list[dict[str, Any]], name: str, today: date) -> dict[str, Any]:
    cutoff = datetime(
        today.year, today.month, today.day, tzinfo=timezone.utc,
    ) - timedelta(days=7)
    count = fails = 0
    for e in entries:
        if e.get("metric") != name:
            continue
        try:
            ts = datetime.fromisoformat(str(e.get("timestamp", "")))
        except ValueError:
            continue
        if ts < cutoff:
            continue
        count += 1
        if e.get("status") != "success":
            fails += 1
    return {"queries_7d": count, "failures_7d": fails}


def metric_health(
    metric_store: MetricStore,
    schema_store: SchemaStore,
    executor: Any,
    qlog_entries: list[dict[str, Any]],
    subs: list[dict[str, Any]],
    today: date,
    ds_type: str = "hive",
) -> list[dict[str, Any]]:
    """One health row per defined metric, worst problems first."""
    from .subscriptions import _max_time_value

    rows: list[dict[str, Any]] = []
    for metric in metric_store.metrics:
        row: dict[str, Any] = {
            "metric": metric.name,
            "display_name": metric.display_name,
        }
        # freshness: max(time_column) per underlying table
        try:
            max_by_table = _max_time_value(
                metric, metric_store, schema_store, executor, ds_type,
            )
            worst = min(
                (d for d in max_by_table.values() if d is not None),
                default=None,
            )
            row["latest_day"] = worst.isoformat() if worst else None
            row["lag_days"] = (
                (today - worst).days - 1 if worst else None
            )
        except Exception as exc:
            row["freshness_error"] = str(exc)[:120]
        # subscriptions on this metric + active alert state
        mine = [
            s for s in subs
            if s.get("metric") == metric.name
            or metric.name in (s.get("metrics") or [])
        ]
        row["subscriptions"] = len(mine)
        active = [
            s for s in mine if (s.get("alert_state") or {}).get("active")
        ]
        row["alerting"] = bool(active)
        if active:
            row["alerting_since"] = active[0]["alert_state"].get("since", "")
        # 7-day query stats from qlog
        row.update(_qlog_7d(qlog_entries, metric.name, today))
        # month-target completion (only when declared; 1 SQL)
        target = metric.targets.get("month")
        if target:
            try:
                yesterday = today - timedelta(days=1)
                sql = build_metric_sql(
                    metric, metric_store, schema_store,
                    time_range=TimeRange(
                        start=yesterday.replace(day=1), end=yesterday,
                    ),
                )
                validation = validate_sql(sql, schema_store)
                if not validation.ok:
                    raise ValueError("; ".join(validation.errors))
                result = executor.run(
                    enforce_limit(sql, dialect=ds_type), max_rows=10,
                )
                actual = (
                    float(result.rows[0][-1])
                    if result.rows and result.rows[0][-1] is not None else 0.0
                )
                row["month_completion_pct"] = round(actual / target * 100, 1)
            except Exception as exc:
                row["target_error"] = str(exc)[:120]
        # status rollup: red = stale/alerting/broken, yellow = failures, green
        stale = row.get("lag_days") is not None and row["lag_days"] > 1
        broken = "freshness_error" in row or "target_error" in row
        if stale or row["alerting"] or broken:
            row["status"] = "red"
        elif row["failures_7d"]:
            row["status"] = "yellow"
        else:
            row["status"] = "green"
        rows.append(row)
    order = {"red": 0, "yellow": 1, "green": 2}
    rows.sort(key=lambda r: (order[r["status"]], r["metric"]))
    return rows
