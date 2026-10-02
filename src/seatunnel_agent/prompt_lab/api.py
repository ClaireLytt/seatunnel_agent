# -*- coding: utf-8 -*-
"""REST API for the prompt lab — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).

  POST /api/promptlab/run      — run one prompt across profiles
  GET  /api/promptlab/profiles — list profile NAMES (never their contents:
                                 profiles hold decrypted API keys)
  GET  /api/promptlab/health   — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..settings_store import list_profiles
from .report import normalize_lang, render_matrix_markdown
from .runner import ACTIVE, run_matrix

router = APIRouter(prefix="/api/promptlab", tags=["prompt_lab"])


class RunRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: str | None = Field(None, description="Optional system prompt")
    profiles: list[str] = Field(default_factory=lambda: [ACTIVE])
    parallel: bool = False
    lang: str = "zh"
    report: bool = Field(False, description="Include the markdown report")


class RunResponse(BaseModel):
    cells: list[dict[str, Any]]
    report: str | None = None
    all_failed: bool
    elapsed_ms: int


@router.post("/run", response_model=RunResponse)
def run(req: RunRequest) -> RunResponse:
    start = time.time()
    try:
        result = run_matrix(req.prompt, system=req.system,
                            profiles=req.profiles, parallel=req.parallel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RunResponse(
        cells=[c.to_dict() for c in result.cells],
        report=(render_matrix_markdown(result, normalize_lang(req.lang))
                if req.report else None),
        all_failed=result.all_failed,
        elapsed_ms=int((time.time() - start) * 1000),
    )


@router.get("/profiles")
def profiles() -> dict[str, list[str]]:
    # Names only — the profile payloads contain decrypted secrets.
    return {"profiles": [ACTIVE] + list_profiles()}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "prompt_lab"}
