"""REST API for the code-fix agent — FastAPI router.

The agent edits local files and runs pytest, so unlike the other agents
this surface is OFF by default: every request is refused (403) unless
``CODEFIX_API_ALLOWED_DIRS`` (``os.pathsep``-separated directories) is
configured AND the target path resolves inside one of them.  The HTTP
surface never exposes ``in_place`` — runs always use the engine's
isolated git worktree.

  POST /api/codefix/run    — run one fix, SSE step/done stream
  GET  /api/codefix/health — health check
"""

from __future__ import annotations

import json
import os
import queue
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health

router = APIRouter(prefix="/api/codefix", tags=["code_fix"])

_NO_KEY = {
    "en": "No LLM configured — set an API key on the Settings page first.",
    "zh": "未配置 LLM — 请先到设置页配置 API key。",
}


class RunRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Project directory")
    tests: str = Field("", description="Optional pytest selector")
    instruction: str = Field("", description="Optional fix instruction")
    max_steps: int = Field(12, ge=2, le=30)
    lang: str = "zh"


def _allowed_dirs() -> list[Path]:
    raw = os.getenv("CODEFIX_API_ALLOWED_DIRS", "")
    return [Path(p).resolve() for p in raw.split(os.pathsep) if p.strip()]


def _guard(path: str) -> Path:
    """Mandatory whitelist: no env → 403; outside the whitelist → 403."""
    allowed = _allowed_dirs()
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="code-fix API is disabled: set CODEFIX_API_ALLOWED_DIRS")
    target = Path(path).resolve()
    for root in allowed:
        if target == root or target.is_relative_to(root):
            return target
    raise HTTPException(status_code=403,
                        detail=f"path not under CODEFIX_API_ALLOWED_DIRS: "
                               f"{target}")


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/run")
def run(req: RunRequest) -> StreamingResponse:
    """One fix run as an SSE stream: a ``step`` event per tool call,
    then one terminal ``done`` (or ``error``) event.  Always runs in the
    engine's isolated worktree (``in_place`` is not exposed over HTTP)."""
    from seatunnel_agent.agents.ai.code_fix.report import normalize_lang
    target = _guard(req.path)
    lang = normalize_lang(req.lang)

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

        from .engine import fix
        events: queue.Queue = queue.Queue()
        outcome: dict[str, Any] = {}

        def work() -> None:
            try:
                outcome["result"] = fix(
                    target, settings, tests=req.tests.strip(),
                    instruction=req.instruction,
                    max_steps=req.max_steps, on_step=events.put)
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
        yield _sse({"type": "done", **outcome["result"].to_dict()})

    return StreamingResponse(stream(), media_type="text/event-stream")


add_health(router, "code_fix")
