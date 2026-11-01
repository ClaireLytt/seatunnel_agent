"""REST API for the execution-plan analyzer — FastAPI router.

  POST /api/sqlperf/analyze — plan facts + severity-ranked findings
  GET  /api/sqlperf/health  — health check
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .analyzer import analyze
from .report import render_markdown

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


def _core(req: AnalyzeRequest, resolve):
    """Returns (after-plan report, before-plan report | None)."""
    result = analyze(resolve(req.file, req.text, "'file' or 'text'"))
    before = None
    if (req.before_file or "").strip() or req.before_text.strip():
        raw = resolve(req.before_file, req.before_text,
                      "'before_file' or 'before_text'")
        try:
            before = analyze(raw)
        except Exception as exc:  # bad input
            raise HTTPException(status_code=400,
                                detail=f"before plan: {exc}") from exc
    return result, before


def _post(req: AnalyzeRequest, result, payload, lang: str) -> list[str]:
    after, before = result
    if before is None:
        return []
    from .diff import diff_plans, render_diff

    payload["diff"] = diff_plans(before, after)
    return [render_diff(payload["diff"], lang=lang)]


def _llm(req: AnalyzeRequest, result, lang: str):
    if not req.sql.strip():
        raise HTTPException(status_code=400, detail="llm=true needs 'sql'")
    from . import advisor_llm
    from .i18n import tp

    rewrite = advisor_llm.rewrite_sql(result[0], req.sql, lang=lang)
    return ("rewrite", rewrite,
            f"### {tp(lang, 'rpt_rewrite')}\n{rewrite}\n")


router = make_text_router(
    prefix="/api/sqlperf", tags=["sql_perf"],
    endpoint="analyze", request_model=AnalyzeRequest,
    health_name="sql_perf", env_var=_ENV,
    core=_core,
    to_payload=lambda result: result[0].to_dict(),
    render=lambda result, req, lang: render_markdown(result[0], lang=lang),
    post=_post,
    llm=_llm,
)
