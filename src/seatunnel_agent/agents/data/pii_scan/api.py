"""REST API for the PII scan agent — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (all deterministic — no LLM, no database, nothing executed):

  POST /api/pii/scan   — scan inline SQL or a whitelisted directory
  POST /api/pii/mask   — masking plan: view DDL for every flagged table
  GET  /api/pii/rules  — built-in rule catalog
  GET  /api/pii/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import (
    add_health,
    ms_since,
    require_dir,
)
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
    try:
        if (req.dir or "").strip():
            target = require_dir(req.dir or "",
                                            "PII_API_ALLOWED_DIRS")
            result = scan_dir(target, dialect=req.dialect)
        else:
            result = scan_sql_text(req.sql or "", dialect=req.dialect)
    except HTTPException:
        raise
    except Exception as exc:  # legacy UI degraded to "⚠️ Type: msg"
        raise HTTPException(status_code=400, detail={
            "code": "scan_failed",
            "error": f"{type(exc).__name__}: {exc}"})
    return PiiScanResponse(
        result=report_to_dict(result, lang),
        report=render_markdown(result, lang) if req.report else None,
        elapsed_ms=ms_since(start),
    )


class PiiMaskRequest(BaseModel):
    sql: str | None = Field(None, description="Inline SQL script")
    dir: str | None = Field(None, description="Directory scanned recursively for *.sql")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    min_confidence: str = Field(
        "low", description="Lowest confidence to mask: 'low' or 'high'")


class PiiMaskResponse(BaseModel):
    result: dict[str, Any]
    sql: str
    elapsed_ms: int


@router.post("/mask", response_model=PiiMaskResponse)
def mask(req: PiiMaskRequest) -> PiiMaskResponse:
    """Disposal half of the scanner: CREATE VIEW DDL with masked columns."""
    from .masker import plan_dir, plan_sql_text, render_mask_sql

    start = time.time()
    if not (req.sql or "").strip() and not (req.dir or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'sql' or 'dir'")
    if req.min_confidence not in ("low", "high"):
        raise HTTPException(status_code=400,
                            detail="min_confidence must be 'low' or 'high'")
    try:
        if (req.dir or "").strip():
            target = require_dir(req.dir or "", "PII_API_ALLOWED_DIRS")
            plan = plan_dir(target, dialect=req.dialect,
                            min_confidence=req.min_confidence)
        else:
            plan = plan_sql_text(req.sql or "", dialect=req.dialect,
                                 min_confidence=req.min_confidence)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "code": "mask_failed",
            "error": f"{type(exc).__name__}: {exc}"})
    return PiiMaskResponse(result=plan.to_dict(),
                           sql=render_mask_sql(plan),
                           elapsed_ms=ms_since(start))


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
