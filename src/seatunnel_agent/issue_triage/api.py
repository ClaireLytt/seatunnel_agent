# -*- coding: utf-8 -*-
"""REST API for issue triage — FastAPI router.

  POST /api/triage/run    — triage an inline issue (optional inline history)
  GET  /api/triage/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .engine import triage
from .report import normalize_lang, render_markdown

router = APIRouter(prefix="/api/triage", tags=["issue_triage"])


class TriageRequest(BaseModel):
    title: str = Field(..., min_length=1)
    body: str = Field("", description="Issue body")
    issues: list[dict[str, Any]] = Field(
        default_factory=list,
        description="History issues [{number,title,body,labels}] for dedupe")
    lang: str = "zh"
    report: bool = Field(False, description="Include the markdown report")


class TriageResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/run", response_model=TriageResponse)
def run(req: TriageRequest) -> TriageResponse:
    start = time.time()
    from dotenv import load_dotenv

    from .. import settings_store
    from ..config import load_settings
    load_dotenv()
    settings_store.apply_to_env()
    try:
        settings = load_settings()
    except RuntimeError as exc:  # no API key
        raise HTTPException(status_code=503, detail=str(exc))
    try:
        result = triage(req.title, req.body, settings, issues=req.issues,
                        repo_dir=None)
    except Exception as exc:  # noqa: BLE001 — provider failures
        raise HTTPException(status_code=502,
                            detail=f"{type(exc).__name__}: {exc}")
    return TriageResponse(
        result=result.to_dict(),
        report=(render_markdown(result, normalize_lang(req.lang))
                if req.report else None),
        elapsed_ms=int((time.time() - start) * 1000))


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "issue_triage"}
