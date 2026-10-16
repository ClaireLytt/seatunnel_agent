"""REST API for the batch log inspection agent — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (deterministic — no LLM, nothing executed):

  POST /api/loginspect/scan   — cluster ERROR/WARN events in logs
  GET  /api/loginspect/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since, require_dir
from seatunnel_agent.common.utils import normalize_lang

from .clusterer import DEFAULT_PATTERNS, scan_dir, scan_text
from .report import render_markdown, report_to_dict

router = APIRouter(prefix="/api/loginspect", tags=["log_inspect"])


class LogScanRequest(BaseModel):
    dir: str | None = Field(None, description="Log directory (recursive)")
    text: str | None = Field(None, description="Inline log text to scan")
    patterns: list[str] | None = Field(
        None, description=f"File globs, default {list(DEFAULT_PATTERNS)}")
    include_warn: bool = Field(True, description="Also cluster WARN events")
    top: int = Field(10, ge=1, le=100, description="Clusters to include")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class LogScanResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/scan", response_model=LogScanResponse)
def scan(req: LogScanRequest) -> LogScanResponse:
    start = time.time()
    if not (req.dir or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'dir' or 'text'")
    lang = normalize_lang(req.lang)
    if (req.dir or "").strip():
        target = require_dir(req.dir, "LOGINSPECT_API_ALLOWED_DIRS")
        result = scan_dir(target,
                          patterns=tuple(req.patterns or DEFAULT_PATTERNS),
                          include_warn=req.include_warn)
    else:
        result = scan_text(req.text, include_warn=req.include_warn)
    return LogScanResponse(
        result=report_to_dict(result, top=req.top),
        report=(render_markdown(result, lang, top=req.top)
                if req.report else None),
        elapsed_ms=ms_since(start),
    )


add_health(router, "log_inspect")
