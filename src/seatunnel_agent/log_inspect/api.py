# -*- coding: utf-8 -*-
"""REST API for the batch log inspection agent — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (deterministic — no LLM, nothing executed):

  POST /api/loginspect/scan   — cluster ERROR/WARN events in logs
  GET  /api/loginspect/health — health check
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..api_guard import check_path_allowed
from .clusterer import DEFAULT_PATTERNS, scan_dir, scan_text
from .i18n import normalize_lang
from .report import render_markdown, report_to_dict

router = APIRouter(prefix="/api/loginspect", tags=["log_inspect"])


def _check_dir_allowed(raw_dir: str) -> None:
    """API 是网络入口，目录参数必须限制在白名单内，防任意目录扫描。"""
    check_path_allowed(raw_dir, "LOGINSPECT_API_ALLOWED_DIRS")


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
        target = req.dir.strip()
        _check_dir_allowed(target)
        if not Path(target).is_dir():
            raise HTTPException(status_code=400,
                                detail=f"不是有效目录: {target}")
        result = scan_dir(target,
                          patterns=tuple(req.patterns or DEFAULT_PATTERNS),
                          include_warn=req.include_warn)
    else:
        result = scan_text(req.text, include_warn=req.include_warn)
    return LogScanResponse(
        result=report_to_dict(result, top=req.top),
        report=(render_markdown(result, lang, top=req.top)
                if req.report else None),
        elapsed_ms=int((time.time() - start) * 1000),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "log_inspect"}
