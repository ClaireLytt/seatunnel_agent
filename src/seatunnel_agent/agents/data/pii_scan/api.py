"""REST API for the PII scan agent — a ScanSpec plus two agent-own endpoints.

  POST /api/pii/scan   — scan inline SQL or a whitelisted directory
  POST /api/pii/mask   — masking plan: view DDL for every flagged table
  GET  /api/pii/rules  — built-in rule catalog
  GET  /api/pii/health — health check

``/scan``'s mechanics (whitelist, error envelope, timing, response
envelope) live in :mod:`seatunnel_agent.common.scan_api`; ``/mask`` and
``/rules`` are this agent's own and hang off the same router.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import ms_since, require_dir
from seatunnel_agent.common.scan_api import ScanSpec, make_scan_router

from .report import render_markdown, report_to_dict
from .rules import DEFAULT_RULES
from .scanner import scan_dir, scan_sql_text

SPEC = ScanSpec(
    name="pii_scan",
    prefix="/api/pii",
    whitelist_env="PII_API_ALLOWED_DIRS",
    error_code="scan_failed",   # legacy UI parses this exact code
    # late-bound through module globals so tests can monkeypatch the scanner
    analyze_dir=lambda target, **kw: scan_dir(target, **kw),
    analyze_sql=lambda sql, **kw: scan_sql_text(sql, **kw),
    render=render_markdown,
    to_dict=report_to_dict,     # lang-aware payload
)

router = make_scan_router(SPEC)


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
