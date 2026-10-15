# -*- coding: utf-8 -*-
"""REST API for the Data Skew agent — FastAPI router.

Mount on the Gradio app's FastAPI instance to serve alongside the UI
(``seatunnel-agent ui --api``).  Endpoints:

  POST /api/skew/check  — static skew-pattern analysis of a SQL script
  GET  /api/skew/health — health check

The check is the deterministic static scan: no LLM, no database, nothing
executed — safe to call from CI or other services.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since
from .detector import DIALECTS, _DIALECT_ALIASES
from .history import default_history
from seatunnel_agent.common.utils import normalize_lang

router = APIRouter(prefix="/api/skew", tags=["data_skew"])

_DIALECT_DESC = " | ".join(DIALECTS)


class SkewCheckRequest(BaseModel):
    sql: str = Field(..., min_length=1, description="SQL statement/script to analyze")
    dialect: str = Field("spark", description=_DIALECT_DESC)
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")


class SkewCheckResponse(BaseModel):
    report: str
    findings: list[dict[str, Any]]
    counts: dict[str, int]
    dialect: str
    elapsed_ms: int


@router.post("/check", response_model=SkewCheckResponse)
def check(req: SkewCheckRequest) -> SkewCheckResponse:
    from .agent import static_skew_report
    from .report import render_report

    start = time.time()
    raw = (req.dialect or "spark").strip().lower().replace(" ", "")
    dialect = _DIALECT_ALIASES.get(raw, raw)
    if dialect not in DIALECTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown dialect '{req.dialect}'; expected one of: {_DIALECT_DESC}",
        )
    lang = normalize_lang(req.lang)
    rep = static_skew_report(req.sql, dialect, lang)
    default_history().log(req.sql, rep, mode="static", source="api")
    return SkewCheckResponse(
        report=render_report(rep, lang),
        findings=[f.to_dict() for f in rep.findings],
        counts={"high": len(rep.high), "medium": len(rep.medium),
                "low": len(rep.low)},
        dialect=dialect,
        elapsed_ms=ms_since(start),
    )


add_health(router, "data_skew")
