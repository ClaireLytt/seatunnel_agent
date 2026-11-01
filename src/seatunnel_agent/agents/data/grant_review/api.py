"""REST API for the grant reviewer — FastAPI router.

  POST /api/grantreview/review — scored decisions per application
  GET  /api/grantreview/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .report import render_markdown
from .reviewer import parse_applications, parse_vocabulary, review_grants

_ENV = "GRANTREVIEW_API_ALLOWED_DIRS"


class ReviewRequest(BaseModel):
    application_file: str | None = Field(
        None, description="Application JSON file (object or list)")
    application_text: str = Field("", description="Inline application JSON")
    vocabulary_text: str = Field(
        "", description="Optional custom sensitivity vocabulary JSON "
                        "{\"s3\": [...], \"s2\": [...]} — replaces the "
                        "built-in list per level")
    llm: bool = Field(
        False, description="Also draft per-application replies via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: ReviewRequest, resolve):
    raw = resolve(req.application_file, req.application_text,
                  "'application_file' or 'application_text'")
    vocab = (parse_vocabulary(req.vocabulary_text)
             if req.vocabulary_text.strip() else None)
    return review_grants(parse_applications(raw), vocab=vocab)


def _llm(req: ReviewRequest, result, lang: str):
    from .advisor_llm import review_note
    from .i18n import tp

    note = review_note(result, lang=lang)
    return ("replies", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/grantreview", tags=["grant_review"],
    endpoint="review", request_model=ReviewRequest,
    health_name="grant_review", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
