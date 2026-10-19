"""REST API for the metric consistency checker — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (deterministic — nothing executed):

  POST /api/metricdiff/check  — analyze a whitelisted SQL directory
  GET  /api/metricdiff/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since
from seatunnel_agent.common.utils import normalize_lang

from .differ import check_sql_dir
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
    from pathlib import Path

    from seatunnel_agent.common.api_guard import check_path_allowed

    start = time.time()
    lang = normalize_lang(req.lang)
    target = (req.sql_dir or "").strip()
    # whitelist first (403, no existence probing), then a structured
    # detail the frontend localizes (i18n `bad_dir`)
    check_path_allowed(target, "METRICDIFF_API_ALLOWED_DIRS")
    if not Path(target).is_dir():
        raise HTTPException(status_code=400,
                            detail={"code": "bad_dir", "path": target})
    try:
        result = check_sql_dir(target, dialect=req.dialect)
    except Exception as exc:  # legacy UI degraded to "⚠️ Type: msg"
        raise HTTPException(status_code=400, detail={
            "code": "check_failed",
            "error": f"{type(exc).__name__}: {exc}"})
    return MetricDiffResponse(
        result=report_to_dict(result, lang),
        report=render_markdown(result, lang) if req.report else None,
        elapsed_ms=ms_since(start),
    )


add_health(router, "metric_diff")
