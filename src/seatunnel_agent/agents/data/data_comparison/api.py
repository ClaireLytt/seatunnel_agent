"""REST API for the React Data Comparison page (/api/datacompare).

Ticket 02 surface: session create, page meta (datasource catalog +
defaults), per-side connect and tables listing. State is keyed by a
server-issued ``session_id`` in the per-session connection registry
(``registry.py``) — the seatunnel ``conversation_id`` pattern.

Deliberately imports the Gradio-free modules only (connect/registry/
ui_shared), never ``ui.py``.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from seatunnel_agent.agents.data.data_comparison import actions
from seatunnel_agent.agents.data.data_comparison.connect import connect_side
from seatunnel_agent.agents.data.data_comparison.registry import (
    SessionState,
    get_registry,
)
from seatunnel_agent.agents.data.data_comparison.ui_shared import (
    _NEEDS_AUTH,
    _NEEDS_HOST,
    _PRESETS_STORE,
    _SAMPLE_STRATEGIES,
)
from seatunnel_agent.agents.data.text2sql.executor import (
    DIALECT_NAMES,
    DS_DEFAULTS,
    DS_TYPES,
)

router = APIRouter(prefix="/api/datacompare", tags=["datacompare"])

_SCHEDULE_INTERVALS = ["1", "5", "15", "30", "60"]


def _get_session(session_id: str) -> SessionState:
    session = get_registry().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session_id")
    return session


@router.get("/meta")
def get_meta() -> dict[str, Any]:
    """Static page metadata: datasource catalog, strategies, intervals."""
    return {
        "datasources": [
            {
                "key": ds,
                "label": DIALECT_NAMES[ds],
                "needs_host": ds in _NEEDS_HOST,
                "needs_auth": ds in _NEEDS_AUTH,
                "default_port": DS_DEFAULTS[ds]["port"],
                "default_db": DS_DEFAULTS[ds]["database"],
            }
            for ds in DS_TYPES
        ],
        "sample_strategies": list(_SAMPLE_STRATEGIES),
        "schedule_intervals": _SCHEDULE_INTERVALS,
    }


@router.post("/session")
def create_session() -> dict[str, str]:
    """Issue a new per-tab session in the connection registry."""
    return {"session_id": get_registry().create().session_id}


class ConnectRequest(BaseModel):
    session_id: str
    side: Literal["a", "b"]
    ds_type: str
    host: str = ""
    port: str = ""
    db: str = ""
    username: str = ""
    password: str = ""
    lang: str = "en"


@router.post("/connect")
def connect(req: ConnectRequest) -> dict[str, Any]:
    """Connect one side; stores the executor + tables in the session."""
    session = _get_session(req.session_id)
    result = connect_side(
        session, req.side, req.ds_type,
        req.host, req.port, req.db, req.username, req.password, req.lang,
    )
    if not result.ok:
        return {"ok": False, "error": result.error}
    cfg = result.resolved
    assert cfg is not None  # ok implies a resolved config
    return {
        "ok": True,
        "status": result.status,
        "tables": result.tables or [],
        "resolved": {
            "host": cfg.host,
            "port": cfg.port,
            "database": cfg.database,
        },
    }


class CompareRequest(BaseModel):
    """Core comparison action request.

    The option fields default to the legacy page's defaults; ticket 05
    (options block) plugs real values into the same fields.
    """

    session_id: str
    table_a: str = ""
    table_b: str = ""
    lang: str = "en"
    where: str = ""
    # count
    threshold: str = ""
    # sample
    key_columns: str = ""
    strategy: str = "TOP N"
    column_mapping: str = ""
    masking: bool = True
    stratified_col: str = ""


@router.post("/compare/schema")
def compare_schema(req: CompareRequest) -> dict[str, str]:
    """Schema diff card (HTML fragment; guards return their message as html)."""
    session = _get_session(req.session_id)
    return {"html": actions.compare_schema(
        session, req.table_a, req.table_b, req.lang, req.where)}


@router.post("/compare/count")
def compare_count(req: CompareRequest) -> dict[str, str]:
    """Row-count comparison card, with optional threshold badge."""
    session = _get_session(req.session_id)
    return {"html": actions.compare_count(
        session, req.table_a, req.table_b, req.lang, req.where,
        req.threshold)}


@router.post("/compare/sample")
def compare_sample(req: CompareRequest) -> dict[str, str]:
    """Sample-data diff card (keyed diff when key columns are given)."""
    session = _get_session(req.session_id)
    return {"html": actions.compare_sample(
        session, req.table_a, req.table_b, req.lang, req.where,
        req.key_columns, req.strategy, req.column_mapping, req.masking,
        req.stratified_col)}


@router.post("/compare/aggregate")
def compare_aggregate(req: CompareRequest) -> dict[str, str]:
    """Aggregate comparison card over shared numeric columns."""
    session = _get_session(req.session_id)
    return {"html": actions.compare_aggregate(
        session, req.table_a, req.table_b, req.lang, req.where)}


@router.get("/tables")
def list_tables(session_id: str, side: Literal["a", "b"]) -> dict[str, Any]:
    """Tables loaded by the last successful connect on *side*."""
    session = _get_session(session_id)
    with session.lock:
        tables = list(getattr(session, f"tables_{side}"))
    return {"tables": tables}


# ── connection presets (ticket 05) ──────────────────────────────────


class PresetSaveRequest(BaseModel):
    name: str
    ds_type: str
    host: str = ""
    port: int = 0
    database: str = ""
    username: str = ""
    password: str = ""
    environment: str = ""


@router.get("/presets")
def list_presets() -> dict[str, Any]:
    """Summaries for the preset dropdowns — never the password."""
    return {
        "presets": [
            {
                "id": p.get("id", ""),
                "name": p.get("name", ""),
                "environment": p.get("environment", ""),
            }
            for p in _PRESETS_STORE.list()
        ]
    }


@router.post("/presets")
def save_preset(req: PresetSaveRequest) -> dict[str, Any]:
    """Save (upsert by name) a connection preset."""
    if req.ds_type not in DS_TYPES:
        raise HTTPException(status_code=400,
                            detail=f"unknown datasource: {req.ds_type}")
    try:
        _PRESETS_STORE.save(
            req.name, req.ds_type, req.host.strip(), req.port,
            req.database.strip(), req.username.strip(),
            req.password.strip(), environment=req.environment.strip(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "name": req.name.strip()}


@router.get("/presets/{name}")
def load_preset(name: str) -> dict[str, Any]:
    """Full preset (password decrypted) to fill the connect form."""
    preset = _PRESETS_STORE.get_by_name(name)
    if preset is None:
        raise HTTPException(status_code=404, detail="unknown preset")
    return {
        "name": preset.get("name", ""),
        "ds_type": preset.get("ds_type", ""),
        "host": preset.get("host", ""),
        "port": preset.get("port", 0),
        "database": preset.get("database", ""),
        "username": preset.get("username", ""),
        "password": preset.get("password", ""),
        "environment": preset.get("environment", ""),
    }


@router.delete("/presets/{name}")
def delete_preset(name: str) -> dict[str, Any]:
    """Delete a preset by name (legacy UI deletes by the selected name)."""
    preset = _PRESETS_STORE.get_by_name(name)
    if preset is None or not _PRESETS_STORE.delete(preset.get("id", "")):
        raise HTTPException(status_code=404, detail="unknown preset")
    return {"ok": True}
