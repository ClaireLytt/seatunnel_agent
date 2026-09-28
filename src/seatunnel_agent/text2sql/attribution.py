"""Attribution analysis — "why did the metric move?" (PRD chat_bi section 4).

All arithmetic here is deterministic; the LLM only interprets the result.
For an additive metric and one dimension:

    contribution(v) = (curr_v - prev_v) / |prev_total|

so the contributions sum exactly to the total change rate (self-checkable),
because GROUP BY partitions the rows (NULL dimension values form their own
group). Ratio metrics are decomposed into separate numerator / denominator
attributions (v1 boundary — no two-factor multiplication split).

Query budget: 2 SQLs for the totals + 2 per dimension, so K dimensions cost
2 + 2K queries. The caller supplies ``execute_fn`` so validation, caching
and logging stay in the tool layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .metrics import MetricDef, MetricError, MetricStore, build_metric_sql
from .partition import TimeRange
from .schema import SchemaStore

#: Upper bound on auto-explored dimensions (2 + 2K query budget).
MAX_AUTO_DIMENSIONS = 5

#: Label used for NULL dimension members in breakdown tables.
NULL_LABEL = "(NULL)"

# execute_fn(sql) -> (columns, rows); raises on execution failure.
ExecuteFn = Callable[[str], tuple[list[str], list[tuple]]]


@dataclass
class DimContribution:
    value: str
    prev: float
    curr: float
    delta: float
    contribution: float | None  # delta / |prev_total|; None when prev_total == 0
    is_new: bool = False   # absent in the previous period
    is_gone: bool = False  # absent in the current period


@dataclass
class DimensionBreakdown:
    dimension: str
    rows: list[DimContribution] = field(default_factory=list)
    #: Sum of the top-3 |contribution| — how well this dimension explains
    #: the move; the auto mode picks the dimension maximizing it.
    concentration: float = 0.0
    #: |sum(contributions) - total change rate| <= 1e-6 (identity check).
    check_ok: bool = True


@dataclass
class AttributionResult:
    metric: str
    display_name: str
    unit: str
    prev_label: str
    curr_label: str
    prev_total: float
    curr_total: float
    delta: float
    change_rate: float | None  # None when prev_total == 0
    dimensions: list[DimensionBreakdown] = field(default_factory=list)
    best_dimension: str | None = None
    sql_count: int = 0
    sqls: list[str] = field(default_factory=list)


def _scalar(columns: list[str], rows: list[tuple]) -> float:
    """The single aggregate value of a no-dimension metric query."""
    if not rows or rows[0][-1] is None:
        return 0.0
    try:
        return float(rows[0][-1])
    except (TypeError, ValueError):
        return 0.0


def _breakdown_map(columns: list[str], rows: list[tuple]) -> dict[str, float]:
    """dimension member -> value from a one-dimension metric query."""
    out: dict[str, float] = {}
    for row in rows:
        key = NULL_LABEL if row[0] is None else str(row[0])
        try:
            out[key] = float(row[-1]) if row[-1] is not None else 0.0
        except (TypeError, ValueError):
            out[key] = 0.0
    return out


def _range_label(tr: TimeRange) -> str:
    start = tr.start.isoformat() if tr.start else ""
    end = tr.end.isoformat() if tr.end else ""
    return start if start == end else f"{start}~{end}"


def run_attribution(
    metric: MetricDef,
    store: MetricStore,
    schema_store: SchemaStore,
    execute_fn: ExecuteFn,
    curr_range: TimeRange,
    prev_range: TimeRange,
    dimensions: list[str] | None = None,
    extra_filters: list[str] | None = None,
) -> AttributionResult:
    """Attribute an **additive** metric's move between two periods.

    ``dimensions=None`` explores every allowed dimension (capped at
    :data:`MAX_AUTO_DIMENSIONS`) and picks the most explanatory one.
    Ratio metrics must be decomposed by the caller (see the agent tool).
    """
    if metric.is_ratio:
        raise MetricError(
            f"指标 '{metric.name}' 是比率型，请分别对分子/分母做归因"
        )
    if curr_range.is_empty or prev_range.is_empty:
        raise MetricError("归因分析必须提供当前与对比两个完整时间范围")

    if dimensions:
        allowed = {d.lower() for d in metric.dimensions}
        for d in dimensions:
            if d.lower() not in allowed:
                raise MetricError(
                    f"维度 '{d}' 不在指标 '{metric.name}' 的允许维度中"
                    f"（允许: {', '.join(metric.dimensions) or '无'}）"
                )
        dims = list(dimensions)
    else:
        dims = list(metric.dimensions[:MAX_AUTO_DIMENSIONS])

    sqls: list[str] = []

    def _run(dim: list[str], tr: TimeRange) -> tuple[list[str], list[tuple]]:
        sql = build_metric_sql(
            metric, store, schema_store,
            dimensions=dim, time_range=tr, extra_filters=extra_filters or [],
        )
        sqls.append(sql)
        return execute_fn(sql)

    prev_total = _scalar(*_run([], prev_range))
    curr_total = _scalar(*_run([], curr_range))
    delta = curr_total - prev_total
    change_rate = delta / abs(prev_total) if prev_total else None

    result = AttributionResult(
        metric=metric.name,
        display_name=metric.display_name,
        unit=metric.unit,
        prev_label=_range_label(prev_range),
        curr_label=_range_label(curr_range),
        prev_total=prev_total,
        curr_total=curr_total,
        delta=delta,
        change_rate=change_rate,
    )

    for dim in dims:
        prev_map = _breakdown_map(*_run([dim], prev_range))
        curr_map = _breakdown_map(*_run([dim], curr_range))
        rows: list[DimContribution] = []
        for key in sorted(set(prev_map) | set(curr_map)):
            p = prev_map.get(key, 0.0)
            c = curr_map.get(key, 0.0)
            d = c - p
            rows.append(DimContribution(
                value=key, prev=p, curr=c, delta=d,
                contribution=(d / abs(prev_total)) if prev_total else None,
                is_new=key not in prev_map,
                is_gone=key not in curr_map,
            ))
        rows.sort(key=lambda r: abs(r.delta), reverse=True)

        check_ok = True
        if change_rate is not None:
            total_contrib = sum(r.contribution or 0.0 for r in rows)
            check_ok = abs(total_contrib - change_rate) <= 1e-6
        concentration = sum(
            abs(r.contribution or 0.0) for r in rows[:3]
        )
        result.dimensions.append(DimensionBreakdown(
            dimension=dim, rows=rows,
            concentration=concentration, check_ok=check_ok,
        ))

    if result.dimensions:
        best = max(result.dimensions, key=lambda b: b.concentration)
        result.best_dimension = best.dimension
    result.sql_count = len(sqls)
    result.sqls = sqls
    return result


def breakdown_table(
    breakdown: DimensionBreakdown, max_rows: int = 20,
) -> tuple[list[str], list[tuple]]:
    """Render a breakdown as (columns, rows) for the UI result machinery.

    Column names are stable identifiers: ``prev/curr/delta`` is also the
    waterfall-chart signature detected by ``chart.detect_chart_type``.
    """
    columns = [breakdown.dimension, "prev", "curr", "delta", "contribution_pct"]
    rows: list[tuple] = []
    for r in breakdown.rows[:max_rows]:
        flag = " (新增)" if r.is_new else (" (消失)" if r.is_gone else "")
        rows.append((
            r.value + flag,
            round(r.prev, 4),
            round(r.curr, 4),
            round(r.delta, 4),
            round(r.contribution * 100, 2) if r.contribution is not None else None,
        ))
    return columns, rows


def _fmt(v: float) -> str:
    return f"{v:,.4f}".rstrip("0").rstrip(".")


def render_attribution_markdown(
    results: list[AttributionResult],
    title: str = "",
) -> str:
    """Standalone analysis-report Markdown (专题分析报告 export form).

    ``results`` holds one entry for an additive metric, or the
    numerator/denominator pair of a ratio metric.
    """
    lines: list[str] = []
    head = title or f"{results[0].display_name} 异动归因报告"
    lines.append(f"# {head}")
    lines.append("")
    lines.append(f"> 对比区间: {results[0].prev_label} → {results[0].curr_label}")
    lines.append("> 本报告由确定性计算产出（贡献率之和恒等于总变动率）。")
    for r in results:
        unit = f" {r.unit}" if r.unit else ""
        rate = (f"{r.change_rate * 100:+.2f}%" if r.change_rate is not None
                else "N/A（基期为 0）")
        lines.append("")
        lines.append(f"## {r.display_name} ({r.metric})")
        lines.append("")
        lines.append(f"- 基期: {_fmt(r.prev_total)}{unit} → 当期: "
                     f"{_fmt(r.curr_total)}{unit}")
        lines.append(f"- 变动: {_fmt(r.delta)}{unit} ({rate})")
        if r.best_dimension:
            lines.append(f"- 最优解释维度: **{r.best_dimension}**")
        for b in r.dimensions:
            lines.append("")
            lines.append(f"### 按 {b.dimension} 分解"
                         + ("" if b.check_ok else " ⚠️ 自检未通过"))
            lines.append("")
            lines.append("| 成员 | 基期 | 当期 | 变动 | 贡献率 |")
            lines.append("|---|---|---|---|---|")
            for row in b.rows[:20]:
                flag = " (新增)" if row.is_new else (" (消失)" if row.is_gone else "")
                contrib = (f"{row.contribution * 100:+.2f}%"
                           if row.contribution is not None else "-")
                lines.append(
                    f"| {row.value}{flag} | {_fmt(row.prev)} | {_fmt(row.curr)} "
                    f"| {_fmt(row.delta)} | {contrib} |"
                )
    lines.append("")
    lines.append(f"---\n共执行 {sum(r.sql_count for r in results)} 条 SQL。")
    return "\n".join(lines)


def attribution_to_dict(result: AttributionResult, max_rows: int = 10) -> dict[str, Any]:
    """Compact JSON payload for the agent tool result."""
    return {
        "metric": result.metric,
        "display_name": result.display_name,
        "unit": result.unit,
        "prev_period": result.prev_label,
        "curr_period": result.curr_label,
        "prev_total": round(result.prev_total, 4),
        "curr_total": round(result.curr_total, 4),
        "delta": round(result.delta, 4),
        "change_rate_pct": (
            round(result.change_rate * 100, 2)
            if result.change_rate is not None else None
        ),
        "best_dimension": result.best_dimension,
        "sql_count": result.sql_count,
        "dimensions": [
            {
                "dimension": b.dimension,
                "concentration_pct": round(b.concentration * 100, 2),
                "check_ok": b.check_ok,
                "top_contributors": [
                    {
                        "value": r.value,
                        "prev": round(r.prev, 4),
                        "curr": round(r.curr, 4),
                        "delta": round(r.delta, 4),
                        "contribution_pct": (
                            round(r.contribution * 100, 2)
                            if r.contribution is not None else None
                        ),
                        **({"is_new": True} if r.is_new else {}),
                        **({"is_gone": True} if r.is_gone else {}),
                    }
                    for r in b.rows[:max_rows]
                ],
            }
            for b in result.dimensions
        ],
    }
