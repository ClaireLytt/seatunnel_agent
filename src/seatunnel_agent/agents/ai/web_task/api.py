"""REST API for the web-task agent — FastAPI router.

The agent drives a local browser, so this surface is OFF by default:
every request is refused (403) unless ``WEBTASK_API_ENABLED=1`` is set.
``allow_external`` and ``headed`` are never exposed over HTTP; the only
private target permitted is loopback (the hub driving itself), computed
server-side — everything else stays behind ``validate_start_url``.

  POST /api/webtask/run    — run one browser task, SSE step/done stream
  GET  /api/webtask/health — health check
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health
from seatunnel_agent.common.sse import _NO_KEY, sse_stream

router = APIRouter(prefix="/api/webtask", tags=["web_task"])

_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class RunRequest(BaseModel):
    goal: str = Field(..., min_length=1, description="Browser task goal")
    url: str = Field(..., min_length=1, description="Start URL")
    max_steps: int = Field(15, ge=2, le=30)
    lang: str = "zh"


@router.post("/run")
def run(req: RunRequest) -> StreamingResponse:
    """One browser task as an SSE stream: a ``step`` event per tool
    call, then one terminal ``done`` (or ``error``) event."""
    if os.getenv("WEBTASK_API_ENABLED") != "1":
        raise HTTPException(
            status_code=403,
            detail="web-task API is disabled: set WEBTASK_API_ENABLED=1")
    lang = "zh" if (req.lang or "zh").lower().startswith("zh") else "en"
    # loopback (the hub driving itself) is the page's demo flow; every
    # other private target stays rejected by validate_start_url
    allow_private = (urlparse(req.url).hostname or "") in _LOOPBACK

    from dotenv import load_dotenv

    from seatunnel_agent.common import settings_store
    from seatunnel_agent.common.config import load_settings
    load_dotenv()
    settings_store.apply_to_env()

    def work(emit: Callable[[Any], None]) -> Mapping[str, Any] | None:
        try:
            settings = load_settings()
        except RuntimeError:
            return {"type": "error", "message": _NO_KEY[lang]}

        from .engine import run_task
        result = run_task(
            req.goal.strip(), req.url.strip(), settings,
            max_steps=req.max_steps,
            allow_private=allow_private, on_step=emit)
        return {"type": "done", "success": result.success,
                "reply": result.reply,
                "steps": [s.to_dict() for s in result.steps],
                "truncated": result.truncated,
                "elapsed_ms": result.elapsed_ms}

    return sse_stream(work, map_step=lambda step: {
        "type": "step", "tool": step.tool,
        "elapsed_ms": step.elapsed_ms, "error": step.error})


add_health(router, "web_task")
