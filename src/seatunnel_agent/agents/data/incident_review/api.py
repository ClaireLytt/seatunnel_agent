"""REST API for the incident reviewer — FastAPI router.

  POST /api/incidentreview/review — timeline metrics + graded findings
  GET  /api/incidentreview/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .report import render_markdown
from .reviewer import review_incident

_ENV = "INCIDENTREVIEW_API_ALLOWED_DIRS"


class ReviewRequest(BaseModel):
    data_file: str | None = Field(
        None, description="Incident event log CSV/JSONL file "
                          "(whitelisted dirs)")
    data_text: str = Field("", description="Inline log with columns "
                                           "time/kind/text (kind: impact|"
                                           "alert|action|comm|recovery)")
    llm: bool = Field(
        False, description="Also draft a postmortem via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: ReviewRequest, resolve):
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    headers, rows = parse_rows(raw)
    return review_incident(headers, rows)


def _llm(req: ReviewRequest, result, lang: str):
    from .advisor_llm import postmortem_note
    from .i18n import tp

    note = postmortem_note(result, lang=lang)
    return ("postmortem_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/incidentreview", tags=["incident_review"],
    endpoint="review", request_model=ReviewRequest,
    health_name="incident_review", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
