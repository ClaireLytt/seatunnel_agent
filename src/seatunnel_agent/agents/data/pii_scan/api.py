"""REST API for the PII scan agent — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (all deterministic — no LLM, no database, nothing executed):

  POST /api/pii/scan   — scan inline SQL or a whitelisted directory
  GET  /api/pii/rules  — built-in rule catalog
  GET  /api/pii/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since, require_dir
from seatunnel_agent.common.utils import normalize_lang

from .report import render_markdown, report_to_dict
from .rules import DEFAULT_RULES
from .scanner import scan_dir, scan_sql_text

router = APIRouter(prefix="/api/pii", tags=["pii_scan"])


class PiiScanRequest(BaseModel):
    sql: str | None = Field(None, description="Inline SQL script to scan")
    dir: str | None = Field(None, description="Directory scanned recursively for *.sql")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class PiiScanResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/scan", response_model=PiiScanResponse)
def scan(req: PiiScanRequest) -> PiiScanResponse:
    start = time.time()
    if not (req.sql or "").strip() and not (req.dir or "").strip():
        raise HTTPException(status_code=400,
                            detail="Provide 'sql' or 'dir'")
    lang = normalize_lang(req.lang)
    if (req.dir or "").strip():
        target = require_dir(req.dir or "", "PII_API_ALLOWED_DIRS")
        result = scan_dir(target, dialect=req.dialect)
    else:
        result = scan_sql_text(req.sql or "", dialect=req.dialect)
    return PiiScanResponse(
        result=report_to_dict(result, lang),
        report=render_markdown(result, lang) if req.report else None,
        elapsed_ms=ms_since(start),
    )


@router.get("/rules")
def rules() -> dict[str, Any]:
    return {"rules": [
        {"category": r.category, "severity": r.severity,
         "name_patterns": list(r.name_patterns),
         "weak_patterns": list(r.weak_patterns),
         "comment_keywords": list(r.comment_keywords)}
        for r in DEFAULT_RULES
    ]}


add_health(router, "pii_scan")
