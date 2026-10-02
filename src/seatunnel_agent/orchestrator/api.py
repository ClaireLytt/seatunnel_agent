# -*- coding: utf-8 -*-
"""REST API for the orchestrator — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Stateless: every request is one fresh orchestration (no cross-request
session).  Without a configured LLM the endpoint degrades to deterministic
keyword suggestions.

  POST /api/orchestrator/run    — route one request through the agents
  GET  /api/orchestrator/agents — the routable agent catalog
  GET  /api/orchestrator/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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

    from .. import settings_store
    from ..config import load_settings
    load_dotenv()
    settings_store.apply_to_env()
    try:
        settings = load_settings()
    except RuntimeError:
        catalog = build_catalog(default_lang=req.lang)
        reply = render_suggestions(suggest(req.request, catalog), req.lang)
        return RunResponse(reply=reply, steps=[], truncated=False,
                           suggested_only=True,
                           elapsed_ms=int((time.time() - start) * 1000))
    from .engine import Orchestrator
    try:
        result = Orchestrator(settings, lang=req.lang,
                              max_steps=req.max_steps).run(req.request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — provider/auth/network failures
        raise HTTPException(status_code=503,
                            detail=f"{type(exc).__name__}: {exc}")
    return RunResponse(reply=result.reply,
                       steps=[s.to_dict() for s in result.steps],
                       truncated=result.truncated,
                       elapsed_ms=int((time.time() - start) * 1000))


@router.get("/agents")
def agents(lang: str = "zh") -> dict[str, Any]:
    catalog = build_catalog(default_lang=lang)
    return {"agents": [{
        "name": spec.name,
        "description": spec.description,
        "page": spec.page,
        "input_schema": spec.input_schema,
    } for spec in sorted(catalog.values(), key=lambda s: s.name)]}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "orchestrator"}
