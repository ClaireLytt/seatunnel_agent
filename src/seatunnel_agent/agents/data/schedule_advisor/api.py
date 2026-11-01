"""REST API for the schedule advisor — FastAPI router.

  POST /api/scheduleadvisor/advise — timeline, critical path, margins
  GET  /api/scheduleadvisor/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .advisor import advise_schedule, parse_plan
from .report import render_markdown

_ENV = "SCHEDULEADVISOR_API_ALLOWED_DIRS"


class AdviseRequest(BaseModel):
    plan_file: str | None = Field(
        None, description="Scheduling plan JSON file (whitelisted dirs)")
    plan_text: str = Field("", description="Inline plan JSON")
    llm: bool = Field(
        False, description="Also draft a schedule note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: AdviseRequest, resolve):
    raw = resolve(req.plan_file, req.plan_text,
                  "'plan_file' or 'plan_text'")
    return advise_schedule(parse_plan(raw))


def _llm(req: AdviseRequest, result, lang: str):
    from .advisor_llm import schedule_note
    from .i18n import tp

    note = schedule_note(result, lang=lang)
    return ("schedule_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/scheduleadvisor", tags=["schedule_advisor"],
    endpoint="advise", request_model=AdviseRequest,
    health_name="schedule_advisor", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
