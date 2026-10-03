# -*- coding: utf-8 -*-
"""REST API for CI triage — FastAPI router.

Inline content only: logs are passed as {name, text} items and runs
metadata as a JSON string.  Fetching from GitHub is a CLI affair.

  POST /api/ciinspect/analyze — cluster logs / analyze runs metadata
  GET  /api/ciinspect/health  — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .core import analyze
from .report import normalize_lang, render_markdown

router = APIRouter(prefix="/api/ciinspect", tags=["ci_inspect"])


class LogItem(BaseModel):
    name: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class AnalyzeRequest(BaseModel):
    logs: list[LogItem] = Field(default_factory=list)
    runs_json: str = Field("", description="JSON list of runs metadata")
    top: int = Field(10, ge=1, le=50)
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the markdown report")


class AnalyzeResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_ci(req: AnalyzeRequest) -> AnalyzeResponse:
    start = time.time()
    if not req.logs and not req.runs_json.strip():
        raise HTTPException(status_code=400,
                            detail="Provide logs or runs_json")
    try:
        result = analyze(logs={item.name: item.text for item in req.logs},
                         runs_text=req.runs_json, top=req.top)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return AnalyzeResponse(
        result=result.to_dict(),
        report=(render_markdown(result, normalize_lang(req.lang))
                if req.report else None),
        elapsed_ms=int((time.time() - start) * 1000),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "ci_inspect"}
