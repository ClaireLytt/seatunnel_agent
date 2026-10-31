"""REST API for the execution-plan analyzer — FastAPI router.

  POST /api/sqlperf/analyze — plan facts + severity-ranked findings
  GET  /api/sqlperf/health  — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import (
    add_health,
    ms_since,
    resolve_file_or_text,
)
from seatunnel_agent.common.utils import normalize_lang

from .analyzer import analyze
from .report import render_markdown

router = APIRouter(prefix="/api/sqlperf", tags=["sql_perf"])

_ENV = "SQLPERF_API_ALLOWED_DIRS"


class AnalyzeRequest(BaseModel):
    file: str | None = Field(None, description="EXPLAIN output file")
    text: str | None = Field(None, description="Inline EXPLAIN output")
    before_file: str | None = Field(
        None, description="Pre-optimization EXPLAIN file — adds a "
                          "before/after plan diff")
    before_text: str = Field(
        "", description="Inline pre-optimization EXPLAIN output")
    sql: str = Field("", description="The original SQL — with llm=true "
                                     "an optimized rewrite is drafted")
    llm: bool = Field(False, description="Draft the rewrite via the "
                                         "configured LLM (needs an API "
                                         "key and 'sql')")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class AnalyzeResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/analyze", response_model=AnalyzeResponse)
def run_analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    start = time.time()
    text = resolve_file_or_text(req.file, req.text, _ENV)
    try:
        result = analyze(text)
    except Exception as exc:  # bad input
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    lang = normalize_lang(req.lang)
    report = render_markdown(result, lang=lang) if req.report else None
    payload = result.to_dict()
    if (req.before_file or "").strip() or req.before_text.strip():
        from .diff import diff_plans, render_diff

        before_raw = resolve_file_or_text(req.before_file,
                                          req.before_text or None, _ENV)
        try:
            before = analyze(before_raw)
        except Exception as exc:  # bad input
            raise HTTPException(status_code=400,
                                detail=f"before plan: {exc}") from exc
        payload["diff"] = diff_plans(before, result)
        if report is not None:
            report += "\n\n" + render_diff(payload["diff"], lang=lang)
    if req.llm:
        if not req.sql.strip():
            raise HTTPException(status_code=400,
                                detail="llm=true needs 'sql'")
        from . import advisor_llm
        from .i18n import tp

        try:
            rewrite = advisor_llm.rewrite_sql(result, req.sql, lang=lang)
        except Exception as exc:  # missing key, provider errors
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        payload["rewrite"] = rewrite
        if report is not None:
            report += f"\n\n### {tp(lang, 'rpt_rewrite')}\n{rewrite}\n"
    return AnalyzeResponse(result=payload, report=report,
                           elapsed_ms=ms_since(start))


add_health(router, "sql_perf")
