"""REST API for Text2SQL — FastAPI router (prefix /api/text2sql).

Thin assembler: includes domain sub-routers (favorites, qlog, metrics)
and hosts session-lifecycle / chat / query endpoints that share the
SessionManager.
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

from .api_shared import (
    build_agent,
    entry_or_404,
    session_meta,
    sessions,
)
from .executor import DS_TYPES

router = APIRouter(prefix="/api/text2sql", tags=["text2sql"])

# ── include domain sub-routers ───────────────────────────────────────

from .api_favorites import router as _fav_router
from .api_metrics import router as _metrics_router
from .api_qlog import router as _qlog_router
from .api_templates import router as _tmpl_router

router.include_router(_fav_router)
router.include_router(_qlog_router)
router.include_router(_metrics_router)
router.include_router(_tmpl_router)

# ── Datasources & connect ────────────────────────────────────────────


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


@router.post("/connect")
def connect(req: ConnectRequest) -> dict[str, Any]:
    """Create a server-held session: validate the connection, load schema
    (+ metrics) and keep the agent; credentials travel only on this call."""
    agent = build_agent(req.ds_type, req.db_config, req.schema_ddl,
                        req.metrics_yaml)
    session_id = sessions.create(agent, req)
    entry = sessions.get(session_id)
    assert entry is not None
    entry.extras["full_store"] = agent.runtime.store

    def _warmup() -> None:
        try:
            _ = agent.runtime.retriever
            _ = agent.runtime.executor
        except Exception:
            pass

    threading.Thread(target=_warmup, daemon=True).start()
    return session_meta(session_id, agent)


@router.get("/session/{session_id}")
def session_status(session_id: str) -> dict[str, Any]:
    entry = sessions.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="unknown session")
    return session_meta(session_id, entry.agent)


# ── Chat SSE ─────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    session_id: str
    question: str


class StopRequest(BaseModel):
    session_id: str


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/chat")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    """Stream one chat turn as SSE."""
    entry = sessions.get(req.session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="unknown session")
    agent = entry.agent

    q = sessions.attach_stream(req.session_id)
    if q is None:
        raise HTTPException(status_code=409,
                            detail="a chat turn is already running")

    def on_event(etype: str, data: dict[str, Any]) -> None:
        q.put((etype, data or {}))

    def work() -> None:
        try:
            agent.set_event_hook(on_event)
            agent.chat(req.question)
        except Exception as exc:
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
            sessions.finish_stream(req.session_id, q)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/chat/stop")
def chat_stop(req: StopRequest) -> dict[str, Any]:
    if not sessions.stop(req.session_id):
        raise HTTPException(status_code=404, detail="no active chat")
    return {"stopped": True}


@router.post("/session/{session_id}/reset")
def session_reset(session_id: str) -> dict[str, Any]:
    """New chat: rebuild a fresh agent from the stored connect params."""
    entry = sessions.get(session_id)
    if entry is None or entry.connect is None:
        raise HTTPException(status_code=404, detail="unknown session")
    c = entry.connect
    agent = build_agent(c.ds_type, c.db_config, c.schema_ddl, c.metrics_yaml)
    if sessions.replace_agent(session_id, agent) is None:
        raise HTTPException(status_code=404, detail="unknown session")
    return session_meta(session_id, agent)


# ── Schema ───────────────────────────────────────────────────────────


class FilterRequest(BaseModel):
    tables: list[str]


@router.get("/session/{session_id}/schema")
def schema_list(session_id: str) -> dict[str, Any]:
    entry = entry_or_404(session_id)
    tables = entry.agent.runtime.store.tables
    return {"tables": [
        {"name": t.full_name,
         "column_count": len(t.columns) + len(t.partition_columns),
         "comment": t.comment}
        for t in tables
    ]}


@router.get("/session/{session_id}/schema/{table}")
def schema_detail(session_id: str, table: str) -> dict[str, Any]:
    entry = entry_or_404(session_id)
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
    """Narrow (or widen back) the session's table whitelist."""
    from .api_shared import agent_from_store
    from .metrics import load_metric_store
    from .schema import SchemaStore
    entry = entry_or_404(session_id)
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
    agent = agent_from_store(store, entry.agent.runtime.ds_type,
                             entry.agent.runtime.db_config, metric_store)
    if sessions.replace_agent(session_id, agent) is None:
        raise HTTPException(status_code=404, detail="unknown session")
    return session_meta(session_id, agent)


@router.post("/session/{session_id}/schema/reload")
def schema_reload(session_id: str) -> dict[str, Any]:
    """Re-introspect the datasource; refreshes the full snapshot too."""
    entry = entry_or_404(session_id)
    if entry.connect is None:
        raise HTTPException(status_code=404, detail="unknown session")
    c = entry.connect
    agent = build_agent(c.ds_type, c.db_config, c.schema_ddl,
                        c.metrics_yaml)
    new_entry = sessions.replace_agent(session_id, agent)
    if new_entry is None:
        raise HTTPException(status_code=404, detail="unknown session")
    new_entry.extras["full_store"] = agent.runtime.store
    return session_meta(session_id, agent)


# ── Legacy query + stubs ─────────────────────────────────────────────


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural-language question")
    ds_type: str = Field("hive", description="Data source type")
    db_config: dict[str, Any] | None = Field(
        None, description="Database connection config")
    schema_ddl: str | None = Field(None, description="Inline DDL")
    metrics_yaml: str | None = Field(None, description="Inline metrics.yaml")
    session_id: str | None = Field(None, description="Optional session ID")


class QueryResponse(BaseModel):
    answer: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    elapsed_ms: int


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    start = time.time()

    agent = None
    if req.session_id:
        found = sessions.get(req.session_id)
        agent = found.agent if found else None

    if agent is None:
        agent = build_agent(req.ds_type, req.db_config, req.schema_ddl, req.metrics_yaml)
        if req.session_id:
            sessions.put_legacy(req.session_id, agent)

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

    return QueryResponse(
        answer=answer,
        sql=rt.last_sql or "",
        columns=columns,
        rows=rows,
        row_count=row_count,
        elapsed_ms=ms_since(start),
    )


@router.get("/schema")
def schema() -> dict[str, Any]:
    return {"message": "Use POST /api/text2sql/query with db_config to auto-load schema"}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
