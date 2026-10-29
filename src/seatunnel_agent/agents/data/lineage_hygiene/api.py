"""REST API for the warehouse-hygiene agent — FastAPI router.

  POST /api/hygiene/scan   — analyze inline SQL or a whitelisted directory
  GET  /api/hygiene/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since, require_dir
from seatunnel_agent.common.utils import normalize_lang

from .analyzer import analyze_dir, analyze_sql_text
from .report import render_markdown

router = APIRouter(prefix="/api/hygiene", tags=["lineage_hygiene"])


class HygieneRequest(BaseModel):
    sql: str | None = Field(None, description="Inline SQL script")
    dir: str | None = Field(None, description="Directory scanned recursively for *.sql")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class HygieneResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/scan", response_model=HygieneResponse)
def scan(req: HygieneRequest) -> HygieneResponse:
    start = time.time()
    if not (req.sql or "").strip() and not (req.dir or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'sql' or 'dir'")
    lang = normalize_lang(req.lang)
    try:
        if (req.dir or "").strip():
            target = require_dir(req.dir or "", "HYGIENE_API_ALLOWED_DIRS")
            result = analyze_dir(target, dialect=req.dialect)
        else:
            result = analyze_sql_text(req.sql or "", dialect=req.dialect)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "code": "hygiene_failed",
            "error": f"{type(exc).__name__}: {exc}"})
    return HygieneResponse(
        result=result.to_dict(),
        report=render_markdown(result, lang) if req.report else None,
        elapsed_ms=ms_since(start),
    )


add_health(router, "lineage_hygiene")
