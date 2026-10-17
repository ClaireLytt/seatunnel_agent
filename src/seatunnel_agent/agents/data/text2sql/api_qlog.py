"""Query log, saved sessions, and resume sub-router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .api_shared import entry_or_404

router = APIRouter()


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
    """Restore a saved chat into a live connected session."""
    from .chat_history import load_t2s_session
    entry = entry_or_404(session_id)
    saved = load_t2s_session(req.saved_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="unknown saved session")
    entry.agent.messages = list(saved.agent_messages)
    return {"session_id": session_id, "title": saved.title,
            "chat": saved.chat_messages}
