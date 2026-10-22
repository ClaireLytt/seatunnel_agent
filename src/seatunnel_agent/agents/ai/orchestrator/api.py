"""REST API for the orchestrator — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Stateless: every request is one fresh orchestration (no cross-request
session).  Without a configured LLM the endpoint degrades to deterministic
keyword suggestions.

  POST /api/orchestrator/run           — route one request through the agents
  POST /api/orchestrator/chat          — same, SSE step/done stream (React page)
  GET  /api/orchestrator/session       — last persisted session (restore)
  POST /api/orchestrator/session/clear — persist a "new session" boundary
  GET  /api/orchestrator/agents        — the routable agent catalog
  GET  /api/orchestrator/health        — health check
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since
from seatunnel_agent.common.sse import sse_stream

from .catalog import build_catalog
from .router import render_suggestions, suggest

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])


class RunRequest(BaseModel):
    request: str = Field(..., min_length=1, description="User request")
    lang: str = "zh"
    max_steps: int = Field(5, ge=1, le=10)


class RunResponse(BaseModel):
    reply: str
    steps: list[dict[str, Any]]
    truncated: bool
    suggested_only: bool = False  # true when no LLM was configured
    elapsed_ms: int


@router.post("/run", response_model=RunResponse)
def run(req: RunRequest) -> RunResponse:
    start = time.time()
    from dotenv import load_dotenv

    from seatunnel_agent.common import settings_store
    from seatunnel_agent.common.config import load_settings
    load_dotenv()
    settings_store.apply_to_env()
    try:
        settings = load_settings()
    except RuntimeError:
        catalog = build_catalog(default_lang=req.lang)
        reply = render_suggestions(suggest(req.request, catalog), req.lang)
        return RunResponse(reply=reply, steps=[], truncated=False,
                           suggested_only=True,
                           elapsed_ms=ms_since(start))
    from .engine import Orchestrator
    try:
        result = Orchestrator(settings, lang=req.lang,
                              max_steps=req.max_steps).run(req.request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503,
                            detail=f"{type(exc).__name__}: {exc}")
    return RunResponse(reply=result.reply,
                       steps=[s.to_dict() for s in result.steps],
                       truncated=result.truncated,
                       elapsed_ms=ms_since(start))


class ChatRequest(BaseModel):
    request: str = Field(..., min_length=1, description="User request")
    lang: str = "zh"
    max_steps: int = Field(5, ge=1, le=10)
    session: str | None = None  # restored session id — keep logging under it
    history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Prior plain turns [{role, content}, …] to re-seed "
                    "context after a page refresh")


@router.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    """One orchestration turn as an SSE stream: a ``step`` event per tool
    call while the engine executes, then one terminal ``done`` (or
    ``error``) event.  Stateless like ``/run``: multi-turn context is
    re-seeded from ``history``."""
    from dotenv import load_dotenv

    from seatunnel_agent.common import settings_store
    from seatunnel_agent.common.config import load_settings
    start = time.time()
    load_dotenv()
    settings_store.apply_to_env()

    def work(emit: Callable[[Any], None]) -> Mapping[str, Any] | None:
        try:
            settings = load_settings()
        except RuntimeError:
            catalog = build_catalog(default_lang=req.lang)
            reply = render_suggestions(suggest(req.request, catalog),
                                       req.lang)
            return {"type": "done", "reply": reply, "steps": [],
                    "truncated": False, "suggested_only": True,
                    "session": req.session,
                    "elapsed_ms": ms_since(start)}

        from .engine import Orchestrator
        from .olog import ChatLogger
        orch = Orchestrator(settings, lang=req.lang,
                            max_steps=req.max_steps)
        prior = [(m.get("role", ""), m.get("content", ""))
                 for m in req.history]
        if prior:
            orch.seed_transcript(prior)
        if req.session:
            # keep logging under the restored session so the next page
            # refresh still sees the WHOLE conversation
            orch.session_id = req.session

        result = orch.run(req.request, on_step=emit)
        ChatLogger().log_turn(orch.session_id, req.request, result.reply,
                              [s.to_dict() for s in result.steps])
        return {"type": "done", "reply": result.reply,
                "truncated": result.truncated, "suggested_only": False,
                "session": orch.session_id,
                "elapsed_ms": ms_since(start)}

    return sse_stream(work,
                      map_step=lambda step: {"type": "step",
                                             **step.to_dict()})


@router.get("/session")
def session() -> dict[str, Any]:
    """Most recent persisted session, oldest turn first (page restore)."""
    from .olog import ChatLogger
    turns = ChatLogger().last_session()
    sid = turns[-1].get("session") if turns else None
    return {"session": sid,
            "turns": [{"request": t.get("request", ""),
                       "reply": t.get("reply", ""),
                       "steps": t.get("steps") or []} for t in turns]}


@router.post("/session/clear")
def session_clear() -> dict[str, bool]:
    """A cleared chat must STAY cleared across page refreshes."""
    from .olog import ChatLogger
    ChatLogger().mark_cleared()
    return {"ok": True}


@router.get("/agents")
def agents(lang: str = "zh") -> dict[str, Any]:
    catalog = build_catalog(default_lang=lang)
    return {"agents": [{
        "name": spec.name,
        "description": spec.description,
        "page": spec.page,
        "input_schema": spec.input_schema,
    } for spec in sorted(catalog.values(), key=lambda s: s.name)]}


add_health(router, "orchestrator")
