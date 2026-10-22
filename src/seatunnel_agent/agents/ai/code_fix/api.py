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

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health
from seatunnel_agent.common.sse import _NO_KEY, sse_stream

router = APIRouter(prefix="/api/codefix", tags=["code_fix"])


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

    def work(emit: Callable[[Any], None]) -> Mapping[str, Any] | None:
        try:
            settings = load_settings()
        except RuntimeError:
            return {"type": "error", "message": _NO_KEY[lang]}

        from .engine import fix
        result = fix(target, settings, tests=req.tests.strip(),
                     instruction=req.instruction,
                     max_steps=req.max_steps, on_step=emit)
        return {"type": "done", **result.to_dict()}

    return sse_stream(work, map_step=lambda step: {
        "type": "step", "tool": step.tool,
        "elapsed_ms": step.elapsed_ms, "error": step.error})


add_health(router, "code_fix")
