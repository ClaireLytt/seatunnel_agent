# -*- coding: utf-8 -*-
"""REST API for the metric consistency checker — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (deterministic — nothing executed):

  POST /api/metricdiff/check  — analyze a whitelisted SQL directory
  GET  /api/metricdiff/health — health check
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..api_guard import check_path_allowed
from .differ import check_sql_dir
from .i18n import normalize_lang
from .report import render_markdown, report_to_dict

router = APIRouter(prefix="/api/metricdiff", tags=["metric_diff"])


class MetricDiffRequest(BaseModel):
    sql_dir: str = Field(..., min_length=1,
                         description="Directory scanned recursively for *.sql")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class MetricDiffResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/check", response_model=MetricDiffResponse)
def check(req: MetricDiffRequest) -> MetricDiffResponse:
    start = time.time()
    lang = normalize_lang(req.lang)
    target = req.sql_dir.strip()
    check_path_allowed(target, "METRICDIFF_API_ALLOWED_DIRS")
    if not Path(target).is_dir():
        raise HTTPException(status_code=400, detail=f"不是有效目录: {target}")
    result = check_sql_dir(target, dialect=req.dialect)
    return MetricDiffResponse(
        result=report_to_dict(result, lang),
        report=render_markdown(result, lang) if req.report else None,
        elapsed_ms=int((time.time() - start) * 1000),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "metric_diff"}
