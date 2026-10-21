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

import json
import os
import queue
import threading
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health

router = APIRouter(prefix="/api/webtask", tags=["web_task"])

_NO_KEY = {
    "en": "No LLM configured — set an API key on the Settings page first.",
    "zh": "未配置 LLM — 请先到设置页配置 API key。",
}

_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class RunRequest(BaseModel):
    goal: str = Field(..., min_length=1, description="Browser task goal")
    url: str = Field(..., min_length=1, description="Start URL")
    max_steps: int = Field(15, ge=2, le=30)
    lang: str = "zh"


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


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

    def stream():
        try:
            settings = load_settings()
        except RuntimeError:
            yield _sse({"type": "error", "message": _NO_KEY[lang]})
            return

        from .engine import run_task
        events: queue.Queue = queue.Queue()
        outcome: dict[str, Any] = {}

        def work() -> None:
            try:
                outcome["result"] = run_task(
                    req.goal.strip(), req.url.strip(), settings,
                    max_steps=req.max_steps,
                    allow_private=allow_private, on_step=events.put)
            except Exception as exc:
                outcome["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                events.put(None)  # sentinel

        threading.Thread(target=work, daemon=True).start()
        while True:
            step = events.get()
            if step is None:
                break
            yield _sse({"type": "step", "tool": step.tool,
                        "elapsed_ms": step.elapsed_ms,
                        "error": step.error})

        if "error" in outcome:
            yield _sse({"type": "error", "message": outcome["error"]})
            return
        result = outcome["result"]
        yield _sse({"type": "done", "success": result.success,
                    "reply": result.reply,
                    "steps": [s.to_dict() for s in result.steps],
                    "truncated": result.truncated,
                    "elapsed_ms": result.elapsed_ms})

    return StreamingResponse(stream(), media_type="text/event-stream")


add_health(router, "web_task")
