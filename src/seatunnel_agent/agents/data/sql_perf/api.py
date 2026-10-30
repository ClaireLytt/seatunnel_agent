"""REST API for the execution-plan analyzer — FastAPI router.

  POST /api/sqlperf/analyze — plan facts + severity-ranked findings
  GET  /api/sqlperf/health  — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import (
    add_health,
    ms_since,
    read_whitelisted_file,
)
from seatunnel_agent.common.utils import normalize_lang

from .analyzer import analyze
from .report import render_markdown

router = APIRouter(prefix="/api/sqlperf", tags=["sql_perf"])

_ENV = "SQLPERF_API_ALLOWED_DIRS"


class AnalyzeRequest(BaseModel):
    file: str | None = Field(None, description="EXPLAIN output file")
    text: str | None = Field(None, description="Inline EXPLAIN output")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class AnalyzeResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/analyze", response_model=AnalyzeResponse)
def run_analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    start = time.time()
    if not (req.file or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'file' or 'text'")
    text = (read_whitelisted_file(req.file or "", _ENV)
            if (req.file or "").strip() else req.text or "")
    try:
        result = analyze(text)
    except Exception as exc:  # bad input
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    lang = normalize_lang(req.lang)
    report = render_markdown(result, lang=lang) if req.report else None
    return AnalyzeResponse(result=result.to_dict(), report=report,
                           elapsed_ms=ms_since(start))


add_health(router, "sql_perf")
