"""REST API for the index advisor — FastAPI router.

  POST /api/indexadvisor/recommend — per-table partition/bucket/index picks
  GET  /api/indexadvisor/health    — health check
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
    require_dir,
)
from seatunnel_agent.common.utils import collect_sql_files, normalize_lang

from .advisor import analyze_workload, recommend
from .report import render_markdown

router = APIRouter(prefix="/api/indexadvisor", tags=["index_advisor"])

_ENV = "INDEXADVISOR_API_ALLOWED_DIRS"


class RecommendRequest(BaseModel):
    sql_dir: str | None = Field(
        None, description="Workload directory (recursive *.sql)")
    text: str | None = Field(None, description="Inline multi-statement SQL")
    ddl: str = Field("", description="Optional CREATE TABLE DDL text")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class RecommendResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/recommend", response_model=RecommendResponse)
def run_recommend(req: RecommendRequest) -> RecommendResponse:
    start = time.time()
    if not (req.sql_dir or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400,
                            detail="Provide 'sql_dir' or 'text'")
    if (req.sql_dir or "").strip():
        sql_dir = require_dir(req.sql_dir or "", _ENV)
        files = collect_sql_files(sql_dir)
        text = "\n;\n".join(
            read_whitelisted_file(str(p), _ENV) for p in files)
    else:
        text = req.text or ""
    try:
        advice = recommend(analyze_workload(text, dialect=req.dialect),
                           ddl_text=req.ddl)
    except Exception as exc:  # bad input
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    lang = normalize_lang(req.lang)
    report = render_markdown(advice, lang=lang) if req.report else None
    return RecommendResponse(result=advice.to_dict(), report=report,
                             elapsed_ms=ms_since(start))


add_health(router, "index_advisor")
