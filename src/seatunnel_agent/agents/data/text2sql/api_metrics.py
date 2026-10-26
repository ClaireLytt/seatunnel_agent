"""Metrics catalog, query, and attribution sub-router."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import ms_since

from .api_shared import load_schema_store
from .executor import create_executor
from .metrics import MetricError, build_metric_sql, load_metric_store, ratio_sides

router = APIRouter()


class MetricsQueryRequest(BaseModel):
    metric: str = Field(..., min_length=1, description="Metric name from the catalog")
    dimensions: list[str] = Field(default_factory=list, description="Group-by dimensions")
    start_date: str | None = Field(None, description="Start date, YYYY-MM-DD or yyyyMMdd")
    end_date: str | None = Field(None, description="End date (inclusive)")
    max_partition: str | None = Field(None, description="Partition value when no date range")
    extra_filters: list[str] = Field(default_factory=list, description="Extra SQL conditions")
    execute: bool = Field(False, description="Execute the SQL (requires db_config)")
    ds_type: str = Field("hive", description="Data source type")
    db_config: dict[str, Any] | None = Field(None, description="Database connection config")
    schema_ddl: str | None = Field(None, description="Inline DDL for table definitions")
    metrics_yaml: str | None = Field(
        None, description="Inline metrics.yaml content (defaults to config/metrics.yaml)"
    )


class MetricsQueryResponse(BaseModel):
    metric: str
    sql: str
    executed: bool
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    elapsed_ms: int = 0


@router.get("/metrics")
def list_metrics() -> dict[str, Any]:
    """Metric catalog from config/metrics.yaml (parse-level check only)."""
    store, errors = load_metric_store()
    return {
        "count": len(store),
        "errors": errors,
        "metrics": [
            {
                "name": m.name,
                "display_name": m.display_name,
                "aliases": list(m.aliases),
                "description": m.description,
                "type": m.metric_type,
                "table": m.table,
                "expression": m.expression,
                "numerator": m.numerator,
                "denominator": m.denominator,
                "time_column": m.time_column,
                "dimensions": list(m.dimensions),
                "default_filters": list(m.default_filters),
                "unit": m.unit,
                "owner": m.owner,
            }
            for m in store.metrics
        ],
    }


@router.post("/metrics/query", response_model=MetricsQueryResponse)
def metrics_query(req: MetricsQueryRequest) -> MetricsQueryResponse:
    """Deterministic metric query — no LLM involved."""
    store, db_config = load_schema_store(req.ds_type, req.db_config, req.schema_ddl)
    metric_store, metric_errors = load_metric_store(store, req.metrics_yaml)
    if metric_errors:
        raise HTTPException(
            status_code=400, detail="Invalid metrics: " + "; ".join(metric_errors),
        )
    metric = metric_store.get(req.metric)
    if metric is None:
        known = ", ".join(m.name for m in metric_store.metrics) or "(none)"
        raise HTTPException(
            status_code=404,
            detail=f"Metric '{req.metric}' is not defined. Known: {known}",
        )

    from .metrics import parse_time_range

    try:
        time_range = parse_time_range(req.start_date or "", req.end_date or "")
        sql = build_metric_sql(
            metric, metric_store, store,
            dimensions=req.dimensions,
            time_range=time_range,
            max_partition=(req.max_partition or "").strip() or None,
            extra_filters=req.extra_filters,
        )
    except MetricError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not req.execute:
        return MetricsQueryResponse(metric=metric.name, sql=sql, executed=False)

    if db_config is None:
        raise HTTPException(status_code=400, detail="execute=true requires db_config")

    from .tools import _sanitize_db_error
    from .validator import enforce_limit, validate_sql

    validation = validate_sql(sql, store)
    if not validation.ok:
        raise HTTPException(
            status_code=400, detail="SQL rejected: " + "; ".join(validation.errors),
        )
    final_sql = enforce_limit(sql, dialect=req.ds_type)
    start = time.time()
    try:
        result = create_executor(db_config).run(final_sql, max_rows=1000)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Execution failed: {_sanitize_db_error(str(exc))}",
        )
    from .qlog import QueryLogger
    QueryLogger().log(
        user_query=f"[metrics/query] {metric.name}", generated_sql=final_sql,
        status="success", matched_tables=validation.tables,
        exec_time_ms=result.elapsed_ms, row_count=result.row_count,
        extra={"source": "api", "metric": metric.name},
    )
    return MetricsQueryResponse(
        metric=metric.name,
        sql=final_sql,
        executed=True,
        columns=result.columns,
        rows=[list(r) for r in result.rows],
        row_count=result.row_count,
        elapsed_ms=ms_since(start),
    )


class AttributionRequest(BaseModel):
    metric: str = Field(..., min_length=1, description="Metric name from the catalog")
    curr_start: str = Field(..., description="Current period start, YYYY-MM-DD or yyyyMMdd")
    curr_end: str | None = Field(None, description="Current period end (defaults to curr_start)")
    prev_start: str = Field(..., description="Comparison period start")
    prev_end: str | None = Field(None, description="Comparison period end (defaults to prev_start)")
    dimension: str | None = Field(None, description="Drill only this dimension (default: all allowed)")
    extra_filters: list[str] = Field(default_factory=list, description="Extra SQL conditions")
    ds_type: str = Field("hive", description="Data source type")
    db_config: dict[str, Any] | None = Field(None, description="Database connection config (required)")
    schema_ddl: str | None = Field(None, description="Inline DDL for table definitions")
    metrics_yaml: str | None = Field(
        None, description="Inline metrics.yaml content (defaults to config/metrics.yaml)"
    )


@router.post("/metrics/attribution")
def metrics_attribution(req: AttributionRequest) -> dict[str, Any]:
    """Deterministic attribution analysis — no LLM involved."""
    store, db_config = load_schema_store(req.ds_type, req.db_config, req.schema_ddl)
    if db_config is None:
        raise HTTPException(status_code=400, detail="attribution requires db_config")
    metric_store, metric_errors = load_metric_store(store, req.metrics_yaml)
    if metric_errors:
        raise HTTPException(
            status_code=400, detail="Invalid metrics: " + "; ".join(metric_errors),
        )
    metric = metric_store.get(req.metric)
    if metric is None:
        known = ", ".join(m.name for m in metric_store.metrics) or "(none)"
        raise HTTPException(
            status_code=404,
            detail=f"Metric '{req.metric}' is not defined. Known: {known}",
        )

    from .attribution import attribution_to_dict, run_attribution
    from .metrics import require_time_range
    from .tools import _sanitize_db_error
    from .validator import enforce_limit, validate_sql

    executor = create_executor(db_config)

    def _execute(sql: str) -> tuple[list[str], list[tuple]]:
        validation = validate_sql(sql, store)
        if not validation.ok:
            raise MetricError("SQL rejected: " + "; ".join(validation.errors))
        final_sql = enforce_limit(sql, dialect=req.ds_type)
        result = executor.run(final_sql, max_rows=1000)
        if result.truncated or result.row_count >= 1000:
            raise MetricError(
                "维度基数过大：下钻结果达到 1000 行上限，贡献分解将不完整。"
                "请指定低基数维度（dimension 参数）重试。"
            )
        return result.columns, list(result.rows)

    def _attribute_raw(target):
        return run_attribution(
            target, metric_store, store, _execute,
            curr_range=require_time_range(req.curr_start, req.curr_end or ""),
            prev_range=require_time_range(req.prev_start, req.prev_end or ""),
            dimensions=[req.dimension] if req.dimension else None,
            extra_filters=req.extra_filters,
        )

    try:
        if metric.is_ratio:
            from .attribution import ratio_factor_split

            num, den = ratio_sides(metric, metric_store)
            num_res = _attribute_raw(num)
            den_res = _attribute_raw(den)
            out: dict[str, Any] = {
                "metric": metric.name,
                "type": "ratio",
                "numerator": attribution_to_dict(num_res),
                "denominator": attribution_to_dict(den_res),
            }
            split = ratio_factor_split(
                num_res.prev_total, num_res.curr_total,
                den_res.prev_total, den_res.curr_total,
            )
            if split is not None:
                out["factor_split"] = {
                    k: round(v, 6) if isinstance(v, float) else v
                    for k, v in split.items()
                }
            return out
        return {"type": "additive", **attribution_to_dict(_attribute_raw(metric))}
    except MetricError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Attribution failed: {_sanitize_db_error(str(exc))}",
        )


# ----------------------------------------------------------------------
# forecast / target / correlate — zero-LLM endpoints for orchestration
# (thin shells over the agent tool functions, same runtime semantics)
# ----------------------------------------------------------------------


class _ConnectedRequest(BaseModel):
    ds_type: str = Field("hive", description="Data source type")
    db_config: dict[str, Any] | None = Field(None, description="Database connection config (required)")
    schema_ddl: str | None = Field(None, description="Inline DDL for table definitions")
    metrics_yaml: str | None = Field(
        None, description="Inline metrics.yaml content (defaults to config/metrics.yaml)"
    )


class ForecastRequest(_ConnectedRequest):
    metric: str = Field(..., min_length=1)
    horizon_days: int = Field(7, description="Periods ahead (max 30)")
    grain: str = Field("day", description="day | week | month")
    history_days: int | None = Field(None, description="History window in days")
    end_date: str | None = Field(None, description="Last history day (default: yesterday)")


class TargetProgressRequest(_ConnectedRequest):
    metric: str = Field(..., min_length=1)
    period: str = Field("month", description="month | quarter | year")
    end_date: str | None = Field(None, description="Progress as-of (default: yesterday)")


class TreeAttributionRequest(_ConnectedRequest):
    metric: str = Field(..., min_length=1)
    curr_start: str = Field(..., min_length=1)
    curr_end: str | None = None
    prev_start: str | None = None
    prev_end: str | None = None
    compare_mode: str | None = Field(None, description="mom | wow | yoy")


class CorrelateRequest(_ConnectedRequest):
    metric_a: str = Field(..., min_length=1)
    metric_b: str = Field(..., min_length=1)
    days: int = Field(28, description="Trailing window in days (14-180)")
    end_date: str | None = Field(None, description="Last day (default: yesterday)")


def _tool_runtime(req: _ConnectedRequest):
    from .runtime import Text2SQLRuntime

    store, db_config = load_schema_store(req.ds_type, req.db_config, req.schema_ddl)
    if db_config is None:
        raise HTTPException(status_code=400, detail="this endpoint requires db_config")
    metric_store, metric_errors = load_metric_store(store, req.metrics_yaml)
    if metric_errors:
        raise HTTPException(
            status_code=400, detail="Invalid metrics: " + "; ".join(metric_errors),
        )
    rt = Text2SQLRuntime(
        store=store, metrics=metric_store, ds_type=req.ds_type,
        db_config=db_config,
    )
    rt.source = "api"
    return rt


def _tool_response(out: dict[str, Any]) -> dict[str, Any]:
    if out.get("error"):
        raise HTTPException(status_code=400, detail=out["error"])
    return out


@router.get("/session/{session_id}/metrics/health")
def session_metrics_health(session_id: str) -> dict[str, Any]:
    """Per-metric health rollup on the session's live connection — no LLM."""
    from datetime import date

    from .api_shared import entry_or_404
    from .health import metric_health
    from .qlog import QueryLogger

    rt = entry_or_404(session_id).agent.runtime
    if rt.metrics is None or len(rt.metrics) == 0:
        raise HTTPException(status_code=400, detail="没有指标定义(metrics.yaml)")
    try:
        from .subscriptions import SubscriptionStore

        subs = SubscriptionStore().list()
    except Exception:
        subs = []
    rows = metric_health(
        rt.metrics, rt.store, rt.executor,
        QueryLogger().recent(5000), subs,
        today=date.today(), ds_type=rt.ds_type,
    )
    return {"rows": rows}


@router.post("/metrics/forecast")
def metrics_forecast(req: ForecastRequest) -> dict[str, Any]:
    """Deterministic metric forecast — no LLM involved."""
    from .tools_metric import _tool_forecast_metric

    inp = {
        "metric": req.metric, "horizon_days": req.horizon_days,
        "grain": req.grain, "end_date": req.end_date or "",
    }
    if req.history_days:
        inp["history_days"] = req.history_days
    return _tool_response(_tool_forecast_metric(inp, _tool_runtime(req)))


@router.post("/metrics/target")
def metrics_target(req: TargetProgressRequest) -> dict[str, Any]:
    """Deterministic target-attainment progress — no LLM involved."""
    from .tools_metric import _tool_metric_target_progress

    inp = {
        "metric": req.metric, "period": req.period,
        "end_date": req.end_date or "",
    }
    return _tool_response(_tool_metric_target_progress(inp, _tool_runtime(req)))


@router.post("/metrics/tree")
def metrics_tree(req: TreeAttributionRequest) -> dict[str, Any]:
    """Deterministic factor-tree decomposition — no LLM involved."""
    from .tools_metric import _tool_tree_attribution

    inp = {
        "metric": req.metric,
        "curr_start": req.curr_start, "curr_end": req.curr_end or "",
        "prev_start": req.prev_start or "", "prev_end": req.prev_end or "",
        "compare_mode": req.compare_mode or "",
    }
    return _tool_response(_tool_tree_attribution(inp, _tool_runtime(req)))


@router.post("/metrics/correlate")
def metrics_correlate(req: CorrelateRequest) -> dict[str, Any]:
    """Deterministic two-metric correlation — no LLM involved."""
    from .tools_metric import _tool_correlate_metrics

    inp = {
        "metric_a": req.metric_a, "metric_b": req.metric_b,
        "days": req.days, "end_date": req.end_date or "",
    }
    return _tool_response(_tool_correlate_metrics(inp, _tool_runtime(req)))
