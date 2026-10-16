"""REST API for the DAG health checker — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (deterministic — nothing executed):

  POST /api/dagcheck/check  — analyze a whitelisted SQL directory
  GET  /api/dagcheck/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since, require_dir
from seatunnel_agent.common.utils import normalize_lang

from .checker import check_sql_dir
from .report import render_markdown, report_to_dict

router = APIRouter(prefix="/api/dagcheck", tags=["dag_check"])


class DagCheckRequest(BaseModel):
    sql_dir: str = Field(..., min_length=1,
                         description="Directory scanned recursively for *.sql")
    seatunnel_dir: str | None = Field(
        None, description="Optional SeaTunnel config directory to merge")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class DagCheckResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/check", response_model=DagCheckResponse)
def check(req: DagCheckRequest) -> DagCheckResponse:
    start = time.time()
    lang = normalize_lang(req.lang)
    for raw in filter(None, (req.sql_dir.strip(),
                             (req.seatunnel_dir or "").strip())):
        require_dir(raw, "DAGCHECK_API_ALLOWED_DIRS")
    result = check_sql_dir(
        req.sql_dir.strip(), dialect=req.dialect,
        seatunnel_dir=(req.seatunnel_dir or "").strip() or None)
    return DagCheckResponse(
        result=report_to_dict(result, lang),
        report=render_markdown(result, lang) if req.report else None,
        elapsed_ms=ms_since(start),
    )


add_health(router, "dag_check")
