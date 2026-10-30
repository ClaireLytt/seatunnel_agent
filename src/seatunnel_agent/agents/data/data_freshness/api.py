"""REST API for the data freshness agent — FastAPI router.

  POST /api/freshness/scan   — per-table late/stalled/stale verdicts
  GET  /api/freshness/health — health check
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

from .checker import parse_events, parse_rules, scan
from .report import render_markdown, scan_to_dict

router = APIRouter(prefix="/api/freshness", tags=["data_freshness"])


class ScanRequest(BaseModel):
    file: str | None = Field(
        None, description="Update-event inventory file (.json/.csv)")
    text: str | None = Field(None, description="Inline JSON/CSV inventory")
    rules_file: str | None = Field(
        None, description="Freshness rules file (JSON)")
    rules_text: str | None = Field(None, description="Inline rules JSON")
    now: str | None = Field(
        None, description="Evaluation time, ISO timestamp "
                          "(default: latest update seen)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class ScanResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/scan", response_model=ScanResponse)
def run_scan(req: ScanRequest) -> ScanResponse:
    start = time.time()
    if not (req.file or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'file' or 'text'")
    if (req.file or "").strip():
        text = read_whitelisted_file(req.file or "",
                                     "FRESHNESS_API_ALLOWED_DIRS")
    else:
        text = req.text or ""
    if (req.rules_file or "").strip():
        rules_text = read_whitelisted_file(req.rules_file or "",
                                           "FRESHNESS_API_ALLOWED_DIRS")
    else:
        rules_text = req.rules_text or ""
    try:
        result = scan(parse_events(text), parse_rules(rules_text),
                      now=(req.now or "").strip() or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    lang = normalize_lang(req.lang)
    return ScanResponse(
        result=scan_to_dict(result),
        report=render_markdown(result, lang) if req.report else None,
        elapsed_ms=ms_since(start),
    )


add_health(router, "data_freshness")
