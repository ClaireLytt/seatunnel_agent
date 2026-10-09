# -*- coding: utf-8 -*-
"""REST API for the cost advisor agent — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (deterministic — no LLM, no database, nothing executed):

  POST /api/cost/analyze — aggregate the query audit log into a cost report
  GET  /api/cost/health  — health check
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..api_guard import check_path_allowed
from .analyzer import analyze_cost
from .i18n import normalize_lang
from .report import render_markdown, report_to_dict

router = APIRouter(prefix="/api/cost", tags=["cost_advisor"])


class CostRequest(BaseModel):
    qlog_path: str | None = Field(
        None, description="Audit log path (default logs/text2sql_queries.jsonl)")
    days: int = Field(30, ge=1, le=365, description="Analysis window in days")
    top_n: int = Field(10, ge=1, le=100, description="Rows per section")
    dialect: str = Field("hive", description="SQL dialect for pattern scan")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown")


class CostResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/analyze", response_model=CostResponse)
def analyze(req: CostRequest) -> CostResponse:
    start = time.time()
    lang = normalize_lang(req.lang)
    qlog = (req.qlog_path or "").strip() or None
    if qlog:
        # API 是网络入口，路径参数必须限制在白名单内，防任意文件读取。
        check_path_allowed(qlog, "COST_API_ALLOWED_DIRS", noun="路径")
        if not Path(qlog).is_file():
            raise HTTPException(status_code=400, detail=f"文件不存在: {qlog}")
    result = analyze_cost(qlog, days=req.days, top_n=req.top_n,
                          dialect=req.dialect)
    rendered = render_markdown(result, lang=lang) if req.report else None
    return CostResponse(
        result=report_to_dict(result, lang=lang),
        report=rendered,
        elapsed_ms=int((time.time() - start) * 1000))


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "cost_advisor"}
