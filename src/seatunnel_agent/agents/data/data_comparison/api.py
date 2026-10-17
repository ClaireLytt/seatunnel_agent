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

from seatunnel_agent.agents.data.data_comparison.connect import connect_side
from seatunnel_agent.agents.data.data_comparison.registry import (
    SessionState,
    get_registry,
)
from seatunnel_agent.agents.data.data_comparison.ui_shared import (
    _NEEDS_AUTH,
    _NEEDS_HOST,
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


@router.get("/tables")
def list_tables(session_id: str, side: Literal["a", "b"]) -> dict[str, Any]:
    """Tables loaded by the last successful connect on *side*."""
    session = _get_session(session_id)
    with session.lock:
        tables = list(getattr(session, f"tables_{side}"))
    return {"tables": tables}
