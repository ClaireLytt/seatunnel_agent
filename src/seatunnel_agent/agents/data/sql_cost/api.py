"""REST API for the SQL cost estimator — FastAPI router.

  POST /api/sqlcost/estimate — the cost card
  GET  /api/sqlcost/health   — health check
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

from .estimator import estimate, parse_stats
from .report import render_markdown

router = APIRouter(prefix="/api/sqlcost", tags=["sql_cost"])

_ENV = "SQLCOST_API_ALLOWED_DIRS"


class EstimateRequest(BaseModel):
    sql: str = Field(..., description="The SQL statement to estimate")
    stats_file: str | None = Field(
        None, description="Table stats inventory file (.json/.csv)")
    stats_text: str = Field("", description="Inline stats inventory")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class EstimateResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/estimate", response_model=EstimateResponse)
def run_estimate(req: EstimateRequest) -> EstimateResponse:
    start = time.time()
    if not req.sql.strip():
        raise HTTPException(status_code=400, detail="Provide 'sql'")
    stats_raw = (read_whitelisted_file(req.stats_file or "", _ENV)
                 if (req.stats_file or "").strip() else req.stats_text)
    if not stats_raw.strip():
        raise HTTPException(status_code=400,
                            detail="Provide 'stats_file' or 'stats_text'")
    try:
        card = estimate(req.sql, parse_stats(stats_raw))
    except Exception as exc:  # bad input, malformed JSON
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    lang = normalize_lang(req.lang)
    report = render_markdown(card, lang=lang) if req.report else None
    return EstimateResponse(result=card.to_dict(), report=report,
                            elapsed_ms=ms_since(start))


add_health(router, "sql_cost")
