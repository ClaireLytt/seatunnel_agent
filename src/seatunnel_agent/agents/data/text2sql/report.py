"""Weekly business report — deterministic skeleton, optional LLM narration.

The skeleton (per-metric weekly totals, WoW change, month-target progress,
currently-alerting subscriptions, and a dimension attribution of the
biggest mover) is pure math over the semantic layer; the LLM, when
available, only rewrites it as prose and is forbidden from inventing or
altering numbers. Without an LLM the table-form skeleton ships as-is.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .metrics import MetricError, MetricStore, build_metric_sql
from .partition import TimeRange
from .schema import SchemaStore
from .validator import enforce_limit, validate_sql

_MAX_METRICS = 10


def build_weekly_skeleton(
    metric_store: MetricStore,
    schema_store: SchemaStore,
    executor: Any,
    subs: list[dict[str, Any]],
    today: date,
    ds_type: str = "hive",
) -> dict[str, Any]:
    """Deterministic weekly numbers: one row per metric plus extras."""
    end = today - timedelta(days=1)
    start = end - timedelta(days=6)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)

    def _total(metric: Any, tr: TimeRange) -> float | None:
        sql = build_metric_sql(metric, metric_store, schema_store, time_range=tr)
        validation = validate_sql(sql, schema_store)
        if not validation.ok:
            raise MetricError("SQL rejected: " + "; ".join(validation.errors))
        result = executor.run(enforce_limit(sql, dialect=ds_type), max_rows=10)
        if not result.rows or result.rows[0][-1] is None:
            return None if metric.is_ratio else 0.0
        return float(result.rows[0][-1])

    rows: list[dict[str, Any]] = []
    for metric in metric_store.metrics[:_MAX_METRICS]:
        row: dict[str, Any] = {
            "metric": metric.name,
            "display_name": metric.display_name,
            "unit": metric.unit,
        }
        try:
            curr = _total(metric, TimeRange(start=start, end=end))
            prev = _total(metric, TimeRange(start=prev_start, end=prev_end))
            row["curr"] = curr
            row["prev"] = prev
            if curr is not None and prev not in (None, 0):
                assert prev is not None
                row["wow_pct"] = round((curr - prev) / abs(prev) * 100, 2)
            target = metric.targets.get("month")
            if target and not metric.is_ratio:
                mtd = _total(
                    metric, TimeRange(start=end.replace(day=1), end=end),
                )
                if mtd is not None:
                    row["month_completion_pct"] = round(mtd / target * 100, 1)
        except Exception as exc:
            row["error"] = str(exc)[:120]
        rows.append(row)

    alerting = [
        {
            "name": s.get("name", "?"),
            "metric": s.get("metric", ""),
            "since": (s.get("alert_state") or {}).get("since", ""),
        }
        for s in subs
        if (s.get("alert_state") or {}).get("active")
    ]

    # attribute the biggest additive mover (best-effort, first dimension)
    attribution: dict[str, Any] | None = None
    movers = [
        r for r in rows
        if "wow_pct" in r
        and (m := metric_store.get(r["metric"])) is not None
        and not m.is_ratio and m.dimensions
    ]
    if movers:
        top = max(movers, key=lambda r: abs(r["wow_pct"]))
        top_metric = metric_store.get(top["metric"])
        assert top_metric is not None  # movers filtered on store membership
        try:
            from .attribution import attribution_to_dict, run_attribution

            def _exec(sql: str) -> tuple[list[str], list[tuple]]:
                validation = validate_sql(sql, schema_store)
                if not validation.ok:
                    raise MetricError(
                        "SQL rejected: " + "; ".join(validation.errors))
                result = executor.run(
                    enforce_limit(sql, dialect=ds_type), max_rows=1000,
                )
                return result.columns, list(result.rows)

            attribution = attribution_to_dict(run_attribution(
                top_metric, metric_store, schema_store, _exec,
                curr_range=TimeRange(start=start, end=end),
                prev_range=TimeRange(start=prev_start, end=prev_end),
                dimensions=[top_metric.dimensions[0]],
            ))
            attribution["metric"] = top_metric.name
        except Exception:
            attribution = None

    return {
        "week": {"start": start.isoformat(), "end": end.isoformat()},
        "prev_week": {
            "start": prev_start.isoformat(), "end": prev_end.isoformat(),
        },
        "metrics": rows,
        "alerting": alerting,
        "attribution": attribution,
    }


def render_skeleton_md(sk: dict[str, Any]) -> str:
    """The skeleton as readable Markdown — the no-LLM deliverable."""
    lines = [
        f"# 经营周报 {sk['week']['start']} ~ {sk['week']['end']}",
        "",
        "| 指标 | 本周 | 上周 | 周环比 | 月目标达成 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in sk["metrics"]:
        if r.get("error"):
            lines.append(f"| {r['display_name']} | 计算失败 | — | — | — |")
            continue

        def _fmt(v: float | None) -> str:
            return "无数据" if v is None else f"{v:,.2f}"

        wow = f"{r['wow_pct']:+.1f}%" if "wow_pct" in r else "—"
        tgt = (
            f"{r['month_completion_pct']:g}%"
            if "month_completion_pct" in r else "—"
        )
        lines.append(
            f"| {r['display_name']} | {_fmt(r.get('curr'))} | "
            f"{_fmt(r.get('prev'))} | {wow} | {tgt} |"
        )
    lines.append("")
    if sk["alerting"]:
        lines.append("## 告警中")
        for a in sk["alerting"]:
            lines.append(f"- {a['name']}（{a['metric']}，自 {a['since']}）")
    else:
        lines.append("## 告警中\n\n无")
    attri = sk.get("attribution")
    if attri:
        lines.append("")
        lines.append(f"## 最大变动指标归因：{attri['metric']}")
        for b in attri.get("dimensions", [])[:1]:
            for row in b.get("rows", [])[:3]:
                pct = row.get("contribution_pct")
                pct_txt = f"（贡献 {pct:+.1f}%）" if pct is not None else ""
                lines.append(
                    f"- {row['value']}: {row['delta']:+,.2f}{pct_txt}"
                )
    return "\n".join(lines) + "\n"


_NARRATE_SYSTEM = (
    "你是经营分析助手。把下面的周报数据骨架改写成一段简洁的中文经营摘要"
    "(200 字以内)。硬性约束:只允许使用骨架中出现的数字,禁止改写、"
    "估算或外推任何数值;不确定的事不写;以'数据区间'开头说明周期。"
)


def narrate(skeleton_md: str, settings: Any) -> str | None:
    """LLM prose over the skeleton; None when no LLM is usable."""
    try:
        from seatunnel_agent.common.llm import LLMClient

        client = LLMClient(settings, agent="text2sql")
        resp = client.chat(
            _NARRATE_SYSTEM,
            [{"role": "user", "content": skeleton_md}],
        )
        text = (resp.reply_text or "").strip()
        return text or None
    except Exception:
        return None
