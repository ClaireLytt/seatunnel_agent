"""REST API for the watermark planner — FastAPI router.

  POST /api/watermarkplan/plan — measured lateness + suggested bound
  GET  /api/watermarkplan/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .planner import plan_watermark
from .report import render_markdown

_ENV = "WATERMARKPLAN_API_ALLOWED_DIRS"


class PlanRequest(BaseModel):
    data_file: str | None = Field(
        None, description="Observed events CSV/JSONL file "
                          "(whitelisted dirs)")
    data_text: str = Field("", description="Inline events with columns "
                                           "event_time/arrival_time")
    llm: bool = Field(
        False, description="Also draft a pre-deploy review via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: PlanRequest, resolve):
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    headers, rows = parse_rows(raw)
    return plan_watermark(headers, rows)


def _llm(req: PlanRequest, result, lang: str):
    from .advisor_llm import watermark_note
    from .i18n import tp

    note = watermark_note(result, lang=lang)
    return ("watermark_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/watermarkplan", tags=["watermark_plan"],
    endpoint="plan", request_model=PlanRequest,
    health_name="watermark_plan", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
