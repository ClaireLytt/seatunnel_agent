"""REST API for the Text2SQL agent — FastAPI router.

Mount on the Gradio app's FastAPI instance to serve alongside the UI.
Endpoints:
  POST /api/text2sql/query   — run a natural-language question
  GET  /api/text2sql/schema  — list loaded tables
  GET  /api/text2sql/health  — health check
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import load_settings
from .agent import Text2SQLAgent
from .executor import DS_TYPES, DatabaseConfig, create_executor
from .metrics import MetricError, build_metric_sql, load_metric_store, ratio_sides
from .schema import SchemaStore

router = APIRouter(prefix="/api/text2sql", tags=["text2sql"])

_MAX_SESSIONS = 20


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural-language question")
    ds_type: str = Field("hive", description="Data source type")
    db_config: dict[str, Any] | None = Field(
        None, description="Database connection config: host, port, database, username, password"
    )
    schema_ddl: str | None = Field(None, description="Inline DDL for table definitions")
    metrics_yaml: str | None = Field(
        None, description="Inline metrics.yaml content (defaults to config/metrics.yaml)"
    )
    session_id: str | None = Field(None, description="Optional session ID for multi-turn")


class QueryResponse(BaseModel):
    answer: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    elapsed_ms: int


class _SessionStore:
    """Thread-safe, LRU-bounded session store."""

    def __init__(self, max_size: int = _MAX_SESSIONS) -> None:
        self._max = max_size
        self._store: OrderedDict[str, Text2SQLAgent] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Text2SQLAgent | None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                return self._store[key]
        return None

    def put(self, key: str, agent: Text2SQLAgent) -> None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = agent
            while len(self._store) > self._max:
                self._store.popitem(last=False)


_sessions = _SessionStore()


def _load_schema_store(
    ds_type: str,
    db_config_dict: dict[str, Any] | None,
    schema_ddl: str | None,
) -> tuple[SchemaStore, DatabaseConfig | None]:
    if ds_type not in DS_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported ds_type '{ds_type}'. Valid: {', '.join(DS_TYPES)}",
        )

    store: SchemaStore | None = None
    db_config: DatabaseConfig | None = None

    if db_config_dict:
        from .executor import DS_DEFAULTS
        defaults = DS_DEFAULTS.get(ds_type, {})
        try:
            db_config = DatabaseConfig(
                ds_type=ds_type,
                host=db_config_dict.get("host", "localhost"),
                port=int(db_config_dict.get("port", defaults.get("port", 0))),
                database=db_config_dict.get("database", str(defaults.get("database", "default"))),
                username=db_config_dict.get("username"),
                password=db_config_dict.get("password"),
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid db_config: {exc}")
        executor = create_executor(db_config)
        store = SchemaStore.from_db(executor)

    if schema_ddl:
        from .schema import parse_ddl
        tables = parse_ddl(schema_ddl)
        if store is not None:
            wl_names = {t.full_name.lower() for t in tables}
            filtered = [tb for tb in store.tables if tb.full_name.lower() in wl_names]
            store = SchemaStore(filtered)
        else:
            store = SchemaStore(tables)

    if store is None or len(store) == 0:
        raise HTTPException(status_code=400, detail="No tables loaded — provide db_config or schema_ddl")
    return store, db_config


def _build_agent(
    ds_type: str,
    db_config_dict: dict[str, Any] | None,
    schema_ddl: str | None,
    metrics_yaml: str | None = None,
) -> Text2SQLAgent:
    store, db_config = _load_schema_store(ds_type, db_config_dict, schema_ddl)

    metric_store, metric_errors = load_metric_store(store, metrics_yaml)
    if metrics_yaml and metric_errors:
        raise HTTPException(
            status_code=400,
            detail="Invalid metrics_yaml: " + "; ".join(metric_errors),
        )

    settings = load_settings()
    agent = Text2SQLAgent(
        settings, store=store, ds_type=ds_type, db_config=db_config,
        metric_store=metric_store if len(metric_store) else None,
    )
    agent.runtime.source = "api"  # qlog audit tag
    return agent


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    start = time.time()

    agent: Text2SQLAgent | None = None
    if req.session_id:
        agent = _sessions.get(req.session_id)

    if agent is None:
        agent = _build_agent(req.ds_type, req.db_config, req.schema_ddl, req.metrics_yaml)
        if req.session_id:
            _sessions.put(req.session_id, agent)

    try:
        if agent.messages:
            answer = agent.chat(req.question)
        else:
            answer = agent.run(req.question)
    except Exception as exc:
        from .tools import _sanitize_db_error
        raise HTTPException(
            status_code=500,
            detail=f"Agent execution failed: {_sanitize_db_error(str(exc))}",
        )

    rt = agent.runtime
    columns: list[str] = []
    rows: list[list[Any]] = []
    row_count = 0
    if rt.last_result:
        columns = rt.last_result.columns
        rows = [list(r) for r in rt.last_result.rows]
        row_count = rt.last_result.row_count

    elapsed_ms = int((time.time() - start) * 1000)

    return QueryResponse(
        answer=answer,
        sql=rt.last_sql or "",
        columns=columns,
        rows=rows,
        row_count=row_count,
        elapsed_ms=elapsed_ms,
    )


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
    """Deterministic metric query — no LLM involved.

    Expands the metric into SQL via the semantic layer; optionally executes
    it (validated + LIMIT-enforced) when ``execute`` is true and a
    ``db_config`` is given. Designed as a workflow-tool endpoint (Dify/n8n):
    same inputs always produce identical SQL.
    """
    store, db_config = _load_schema_store(req.ds_type, req.db_config, req.schema_ddl)
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
        elapsed_ms=int((time.time() - start) * 1000),
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
    """Deterministic attribution analysis — no LLM involved.

    Compares the metric between two periods and decomposes the change by
    dimension (contributions sum exactly to the total change rate). Ratio
    metrics return separate numerator/denominator attributions.
    """
    store, db_config = _load_schema_store(req.ds_type, req.db_config, req.schema_ddl)
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
    from .metrics import parse_time_range
    from .tools import _sanitize_db_error
    from .validator import enforce_limit, validate_sql

    executor = create_executor(db_config)

    def _execute(sql: str) -> tuple[list[str], list[tuple]]:
        validation = validate_sql(sql, store)
        if not validation.ok:
            raise MetricError("SQL rejected: " + "; ".join(validation.errors))
        final_sql = enforce_limit(sql, dialect=req.ds_type)
        result = executor.run(final_sql, max_rows=1000)
        # enforce_limit trims at the SQL level: a count AT the limit means
        # the drill-down was (or may have been) cut off.
        if result.truncated or result.row_count >= 1000:
            raise MetricError(
                "维度基数过大：下钻结果达到 1000 行上限，贡献分解将不完整。"
                "请指定低基数维度（dimension 参数）重试。"
            )
        return result.columns, list(result.rows)

    def _attribute_raw(target):
        return run_attribution(
            target, metric_store, store, _execute,
            curr_range=parse_time_range(req.curr_start, req.curr_end or ""),
            prev_range=parse_time_range(req.prev_start, req.prev_end or ""),
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
            # Exact two-factor split (parity with the agent tool) — computed
            # from the raw totals, not the rounded payload.
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


@router.get("/schema")
def schema() -> dict[str, Any]:
    return {"message": "Use POST /api/text2sql/query with db_config to auto-load schema"}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
