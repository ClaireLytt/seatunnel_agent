"""REST API for the batch log inspection agent — FastAPI router.

  POST /api/loginspect/scan    — cluster ERROR/WARN events in logs
  POST /api/loginspect/advice  — LLM root-cause advice on scan results
  GET  /api/loginspect/health  — health check
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


class AdviceRequest(BaseModel):
    dir: str | None = Field(None, description="Log directory (recursive)")
    text: str | None = Field(None, description="Inline log text to scan")
    patterns: list[str] | None = Field(None, description="File globs")
    include_warn: bool = Field(True, description="Also cluster WARN events")
    top: int = Field(5, ge=1, le=50, description="Clusters to advise on")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")


class AdviceResponse(BaseModel):
    advice: str
    elapsed_ms: int


@router.post("/advice", response_model=AdviceResponse)
def advice(req: AdviceRequest) -> AdviceResponse:
    """LLM root-cause advice — requires an API key."""
    start = time.time()
    if not (req.dir or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'dir' or 'text'")
    # Run the scan first
    if (req.dir or "").strip():
        target = require_dir(req.dir or "", "LOGINSPECT_API_ALLOWED_DIRS")
        report = scan_dir(target,
                          patterns=tuple(req.patterns or DEFAULT_PATTERNS),
                          include_warn=req.include_warn)
    else:
        report = scan_text(req.text or "", include_warn=req.include_warn)
    if not report.clusters:
        raise HTTPException(status_code=400,
                            detail="No clusters found — nothing to advise on")
    try:
        from seatunnel_agent.common.config import load_settings

        settings = load_settings()
    except RuntimeError:
        raise HTTPException(status_code=400,
                            detail="No API key configured")
    from .advisor import generate_advice

    lang = normalize_lang(req.lang)
    text = generate_advice(settings, report, lang, top=req.top)
    return AdviceResponse(advice=text or "", elapsed_ms=ms_since(start))


add_health(router, "log_inspect")
