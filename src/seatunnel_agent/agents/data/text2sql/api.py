"""REST API for Text2SQL — FastAPI router (prefix /api/text2sql).

Endpoints: /datasources, /connect, /session/{id}, /session/{id}/reset,
/chat (SSE), /chat/stop, /query, /metrics, /metrics/query,
/metrics/attribution, /schema (stub), /health.

Session state lives in sessions.SessionManager; this module is thin
endpoint wiring.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import ms_since
from seatunnel_agent.common.config import load_settings

from .agent import Text2SQLAgent
from .examples import ExampleStore
from .executor import DS_TYPES, DatabaseConfig, create_executor
from .favorites import FavoritesStore
from .metrics import MetricError, build_metric_sql, load_metric_store, ratio_sides
from .schema import SchemaStore
from .sessions import SessionManager
from .validator import extract_tables

router = APIRouter(prefix="/api/text2sql", tags=["text2sql"])

# ── Favorites ────────────────────────────────────────────────────────

_fav_store = FavoritesStore()


class FavoriteSaveRequest(BaseModel):
    name: str = Field(..., min_length=1)
    sql: str = Field(..., min_length=1)
    question: str = ""
    ds_type: str = ""


class FavoriteRenameRequest(BaseModel):
    name: str = Field(..., min_length=1)


@router.get("/favorites")
def favorites_list() -> dict[str, Any]:
    return {"favorites": _fav_store.list()}


@router.post("/favorites", status_code=201)
def favorites_save(req: FavoriteSaveRequest) -> dict[str, Any]:
    entry = _fav_store.save(req.name, req.sql, req.question, req.ds_type)
    return {"favorite": entry}


@router.patch("/favorites/{fav_id}")
def favorites_rename(fav_id: str, req: FavoriteRenameRequest) -> dict[str, Any]:
    if not _fav_store.rename(fav_id, req.name):
        raise HTTPException(status_code=404, detail="unknown favorite")
    return {"renamed": True}


@router.delete("/favorites/{fav_id}")
def favorites_delete(fav_id: str) -> dict[str, Any]:
    if not _fav_store.delete(fav_id):
        raise HTTPException(status_code=404, detail="unknown favorite")
    return {"deleted": True}


# ── Feedback ─────────────────────────────────────────────────────────


class FeedbackRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    sql: str = Field(..., min_length=1)
    positive: bool


@router.post("/feedback")
def feedback(req: FeedbackRequest) -> dict[str, Any]:
    entry = _sessions.get(req.session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="unknown session")
    agent = entry.agent
    rt = agent.runtime

    ex_store: ExampleStore = getattr(agent, "example_store", None) or ExampleStore()

    if req.positive:
        tables = extract_tables(req.sql)
        ex_store.add(req.question, req.sql, tables, source="feedback")
        _fav_store.save(req.question, req.sql, req.question, rt.ds_type)
        rt.logger.log(
            user_query=req.question, generated_sql=req.sql,
            status="feedback_up",
            extra={"source": rt.source, "kind": "feedback"},
        )
    else:
        ex_store.remove_by_question(req.question)
        rt.logger.log(
            user_query=req.question, generated_sql=req.sql,
            status="feedback_down",
            extra={"source": rt.source, "kind": "feedback"},
        )

    return {"ok": True, "positive": req.positive}


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


_sessions = SessionManager()


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

    return _agent_from_store(store, ds_type, db_config, metric_store)


def _agent_from_store(store, ds_type, db_config, metric_store) -> Text2SQLAgent:
    settings = load_settings()
    agent = Text2SQLAgent(
        settings, store=store, ds_type=ds_type, db_config=db_config,
        metric_store=metric_store if len(metric_store) else None,
    )
    agent.runtime.source = "api"  # qlog audit tag
    return agent


@router.get("/datasources")
def datasources() -> dict[str, Any]:
    """Supported dialects + per-dialect env-derived connection defaults
    (never the password) — the UI's dropdown source and prefill."""
    from .executor import config_from_env
    out = []
    for ds in DS_TYPES:
        defaults: dict[str, str] = {}
        cfg = config_from_env(ds)
        if cfg is not None:
            defaults = {"host": cfg.host, "port": str(cfg.port),
                        "database": cfg.database or ""}
            if cfg.username:
                defaults["username"] = cfg.username
        out.append({"ds_type": ds, "defaults": defaults})
    return {"datasources": out}


class ConnectRequest(BaseModel):
    ds_type: str
    db_config: dict[str, Any] | None = None
    schema_ddl: str | None = None
    metrics_yaml: str | None = None


def _session_meta(session_id: str, agent: Text2SQLAgent) -> dict[str, Any]:
    tables = [t.full_name for t in agent.runtime.store.tables]
    return {
        "session_id": session_id,
        "ds_type": agent.runtime.ds_type,
        "table_count": len(tables),
        "tables": tables,
    }


@router.post("/connect")
def connect(req: ConnectRequest) -> dict[str, Any]:
    """Create a server-held session: validate the connection, load schema
    (+ metrics) and keep the agent; credentials travel only on this call."""
    agent = _build_agent(req.ds_type, req.db_config, req.schema_ddl,
                         req.metrics_yaml)
    session_id = _sessions.create(agent, req)
    entry = _sessions.get(session_id)
    assert entry is not None
    entry.extras["full_store"] = agent.runtime.store

    def _warmup() -> None:
        # touch the lazy retriever/executor so the first query doesn't pay
        # for them; LLM warmup belongs to the query path (#65)
        try:
            _ = agent.runtime.retriever
            _ = agent.runtime.executor
        except Exception:
            pass  # best-effort; connect already validated the connection

    threading.Thread(target=_warmup, daemon=True).start()
    return _session_meta(session_id, agent)


@router.get("/session/{session_id}")
def session_status(session_id: str) -> dict[str, Any]:
    entry = _sessions.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="unknown session")
    return _session_meta(session_id, entry.agent)


class ChatRequest(BaseModel):
    session_id: str
    question: str


class StopRequest(BaseModel):
    session_id: str


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/chat")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Stream one chat turn as SSE: text / result (execute_sql snapshots) /
    final. The agent runs in a worker thread; /chat/stop injects a terminal
    event into the live stream."""
    entry = _sessions.get(req.session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="unknown session")
    agent = entry.agent

    q = _sessions.attach_stream(req.session_id)
    if q is None:
        raise HTTPException(status_code=409,
                            detail="a chat turn is already running")

    def on_event(etype: str, data: dict[str, Any]) -> None:
        q.put((etype, data or {}))

    def work() -> None:
        try:
            agent.set_event_hook(on_event)
            agent.chat(req.question)
        except Exception as exc:  # surfaced as an SSE event
            q.put(("error", {"message": f"{type(exc).__name__}: {exc}"}))
        finally:
            agent.set_event_hook(None)
            q.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        try:
            while True:
                item = q.get()
                if item is None:
                    break
                etype, data = item
                if etype == "text" or etype == "thinking":
                    yield _sse({"type": "text", "text": data.get("text", "")})
                elif etype == "text_delta":
                    yield _sse({"type": "delta",
                                "text": data.get("text", "")})
                elif etype == "tool_call":
                    yield _sse({"type": "tool_call",
                                "name": data.get("name", "")})
                elif etype == "tool_result" and data.get("name") == "execute_sql":
                    from .chart import result_snapshot
                    yield _sse(result_snapshot(data.get("result")))
                elif etype == "final_answer":
                    yield _sse({"type": "final",
                                "text": data.get("text", ""),
                                **({"stopped": True} if data.get("stopped")
                                   else {})})
                    break
                elif etype == "error":
                    yield _sse({"type": "error",
                                "message": data.get("message", "")})
                    break
        finally:
            _sessions.finish_stream(req.session_id, q)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/chat/stop")
def chat_stop(req: StopRequest) -> dict[str, Any]:
    if not _sessions.stop(req.session_id):
        raise HTTPException(status_code=404, detail="no active chat")
    return {"stopped": True}


@router.post("/session/{session_id}/reset")
def session_reset(session_id: str) -> dict[str, Any]:
    """New chat: rebuild a fresh agent from the stored connect params."""
    entry = _sessions.get(session_id)
    if entry is None or entry.connect is None:
        raise HTTPException(status_code=404, detail="unknown session")
    c = entry.connect
    agent = _build_agent(c.ds_type, c.db_config, c.schema_ddl, c.metrics_yaml)
    if _sessions.replace_agent(session_id, agent) is None:
        raise HTTPException(status_code=404, detail="unknown session")
    return _session_meta(session_id, agent)


class FilterRequest(BaseModel):
    tables: list[str]


def _entry_or_404(session_id: str):
    entry = _sessions.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="unknown session")
    return entry


@router.get("/session/{session_id}/schema")
def schema_list(session_id: str) -> dict[str, Any]:
    entry = _entry_or_404(session_id)
    tables = entry.agent.runtime.store.tables
    return {"tables": [
        {"name": t.full_name,
         "column_count": len(t.columns) + len(t.partition_columns),
         "comment": t.comment}
        for t in tables
    ]}


@router.get("/session/{session_id}/schema/{table}")
def schema_detail(session_id: str, table: str) -> dict[str, Any]:
    entry = _entry_or_404(session_id)
    t = entry.agent.runtime.store.get(table)
    if t is None:
        raise HTTPException(status_code=404, detail="unknown table")
    return {"name": t.full_name, "comment": t.comment,
            "columns": [{"name": c.name, "type": c.dtype,
                         "comment": c.comment} for c in t.columns],
            "partition_columns": [{"name": c.name, "type": c.dtype}
                                  for c in t.partition_columns]}


@router.post("/session/{session_id}/schema/filter")
def schema_filter(session_id: str, req: FilterRequest) -> dict[str, Any]:
    """Narrow (or widen back) the session's table whitelist; the full
    snapshot taken at connect is the widening source."""
    from .schema import SchemaStore
    entry = _entry_or_404(session_id)
    full = entry.extras.get("full_store") or entry.agent.runtime.store
    wanted = []
    for name in req.tables:
        t = full.get(name)
        if t is None:
            raise HTTPException(status_code=400,
                                detail=f"unknown table: {name}")
        wanted.append(t)
    if not wanted:
        raise HTTPException(status_code=400, detail="empty table filter")
    c = entry.connect
    store = SchemaStore(wanted)
    metric_store, _ = load_metric_store(
        store, c.metrics_yaml if c else None)
    agent = _agent_from_store(store, entry.agent.runtime.ds_type,
                              entry.agent.runtime.db_config, metric_store)
    if _sessions.replace_agent(session_id, agent) is None:
        raise HTTPException(status_code=404, detail="unknown session")
    return _session_meta(session_id, agent)


@router.post("/session/{session_id}/schema/reload")
def schema_reload(session_id: str) -> dict[str, Any]:
    """Re-introspect the datasource; refreshes the full snapshot too."""
    entry = _entry_or_404(session_id)
    if entry.connect is None:
        raise HTTPException(status_code=404, detail="unknown session")
    c = entry.connect
    agent = _build_agent(c.ds_type, c.db_config, c.schema_ddl,
                         c.metrics_yaml)
    new_entry = _sessions.replace_agent(session_id, agent)
    if new_entry is None:
        raise HTTPException(status_code=404, detail="unknown session")
    new_entry.extras["full_store"] = agent.runtime.store
    return _session_meta(session_id, agent)


def _query_logger():
    from .qlog import QueryLogger
    return QueryLogger()


class QlogDeleteRequest(BaseModel):
    indices: list[int]


class ResumeRequest(BaseModel):
    saved_id: str


@router.get("/history/qlog")
def qlog_list(n: int = 100) -> dict[str, Any]:
    records = _query_logger().recent(n)
    return {"records": list(reversed(records))}


@router.post("/history/qlog/delete")
def qlog_delete(req: QlogDeleteRequest) -> dict[str, Any]:
    return {"deleted": _query_logger().delete(req.indices)}


@router.post("/history/qlog/clear")
def qlog_clear() -> dict[str, Any]:
    _query_logger().clear()
    return {"cleared": True}


@router.get("/history/qlog/export")
def qlog_export() -> Any:
    import csv
    import io

    from fastapi.responses import PlainTextResponse
    records = list(reversed(_query_logger().recent(1000)))
    buf = io.StringIO()
    if records:
        cols = ["timestamp", "user_query", "generated_sql", "status",
                "exec_time_ms", "row_count"]
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)
    return PlainTextResponse(buf.getvalue(), media_type="text/csv")


@router.get("/history/sessions")
def saved_sessions() -> dict[str, Any]:
    from .chat_history import list_t2s_sessions
    return {"sessions": list_t2s_sessions()}


@router.post("/session/{session_id}/resume")
def session_resume(session_id: str, req: ResumeRequest) -> dict[str, Any]:
    """Restore a saved chat into a live connected session: the agent gets
    the saved conversation, the client gets the transcript to replay."""
    from .chat_history import load_t2s_session
    entry = _entry_or_404(session_id)
    saved = load_t2s_session(req.saved_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="unknown saved session")
    entry.agent.messages = list(saved.agent_messages)
    return {"session_id": session_id, "title": saved.title,
            "chat": saved.chat_messages}


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    start = time.time()

    agent: Text2SQLAgent | None = None
    if req.session_id:
        found = _sessions.get(req.session_id)
        agent = found.agent if found else None

    if agent is None:
        agent = _build_agent(req.ds_type, req.db_config, req.schema_ddl, req.metrics_yaml)
        if req.session_id:
            _sessions.put_legacy(req.session_id, agent)

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

    elapsed_ms = ms_since(start)

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
