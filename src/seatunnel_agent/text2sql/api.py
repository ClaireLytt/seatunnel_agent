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


def _build_agent(
    ds_type: str,
    db_config_dict: dict[str, Any] | None,
    schema_ddl: str | None,
) -> Text2SQLAgent:
    if ds_type not in DS_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported ds_type '{ds_type}'. Valid: {', '.join(DS_TYPES)}",
        )

    settings = load_settings()
    store: SchemaStore | None = None
    db_config: DatabaseConfig | None = None

    if db_config_dict:
        try:
            db_config = DatabaseConfig(
                ds_type=ds_type,
                host=db_config_dict.get("host", "localhost"),
                port=int(db_config_dict.get("port", 10000)),
                database=db_config_dict.get("database", "default"),
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

    return Text2SQLAgent(settings, store=store, ds_type=ds_type, db_config=db_config)


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    start = time.time()

    agent: Text2SQLAgent | None = None
    if req.session_id:
        agent = _sessions.get(req.session_id)

    if agent is None:
        agent = _build_agent(req.ds_type, req.db_config, req.schema_ddl)
        if req.session_id:
            _sessions.put(req.session_id, agent)

    try:
        if agent.messages:
            answer = agent.chat(req.question)
        else:
            answer = agent.run(req.question)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}")

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


@router.get("/schema")
def schema() -> dict[str, Any]:
    return {"message": "Use POST /api/text2sql/query with db_config to auto-load schema"}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
