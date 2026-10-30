"""REST API for the slow-query diagnoser — FastAPI router.

  POST /api/slowquery/diagnose — ranked root causes with prescriptions
  GET  /api/slowquery/health   — health check
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

from .diagnoser import diagnose, parse_baseline, parse_metrics
from .report import render_markdown

router = APIRouter(prefix="/api/slowquery", tags=["slow_query"])

_ENV = "SLOWQUERY_API_ALLOWED_DIRS"


class DiagnoseRequest(BaseModel):
    metrics: str = Field(..., description="One run's metrics JSON")
    baseline_file: str | None = Field(
        None, description="History baseline jsonl file")
    baseline_text: str = Field("", description="Inline baseline jsonl")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class DiagnoseResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/diagnose", response_model=DiagnoseResponse)
def run_diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    start = time.time()
    if not req.metrics.strip():
        raise HTTPException(status_code=400, detail="Provide 'metrics'")
    baseline_raw = (read_whitelisted_file(req.baseline_file or "", _ENV)
                    if (req.baseline_file or "").strip()
                    else req.baseline_text)
    try:
        diag = diagnose(parse_metrics(req.metrics),
                        parse_baseline(baseline_raw))
    except Exception as exc:  # bad input, malformed JSON
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    lang = normalize_lang(req.lang)
    report = render_markdown(diag, lang=lang) if req.report else None
    return DiagnoseResponse(result=diag.to_dict(), report=report,
                            elapsed_ms=ms_since(start))


add_health(router, "slow_query")
