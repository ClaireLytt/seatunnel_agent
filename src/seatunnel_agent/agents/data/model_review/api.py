"""REST API for the model reviewer — FastAPI router.

  POST /api/modelreview/review — graded star-schema findings
  GET  /api/modelreview/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .report import render_markdown
from .reviewer import review_model

_ENV = "MODELREVIEW_API_ALLOWED_DIRS"


class ReviewRequest(BaseModel):
    sql_file: str | None = Field(
        None, description="DDL file with CREATE TABLE statements "
                          "(whitelisted dirs)")
    sql_text: str = Field("", description="Inline CREATE TABLE DDL")
    wide_limit: int = Field(50, description="Columns beyond this flag "
                                            "MR006 (wide table)")
    dialect: str = Field("hive", description="SQL dialect for the parser")
    llm: bool = Field(
        False, description="Also draft refactoring advice via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: ReviewRequest, resolve):
    raw = resolve(req.sql_file, req.sql_text, "'sql_file' or 'sql_text'")
    return review_model(raw, dialect=req.dialect, wide_limit=req.wide_limit)


def _llm(req: ReviewRequest, result, lang: str):
    from .advisor_llm import modeling_note
    from .i18n import tp

    note = modeling_note(result, lang=lang)
    return ("modeling_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/modelreview", tags=["model_review"],
    endpoint="review", request_model=ReviewRequest,
    health_name="model_review", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
