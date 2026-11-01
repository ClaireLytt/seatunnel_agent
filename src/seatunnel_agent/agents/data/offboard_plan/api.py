"""REST API for the offboarding planner — FastAPI router.

  POST /api/offboardplan/plan — staged retirement steps
  GET  /api/offboardplan/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .planner import plan_offboard
from .report import render_markdown

_ENV = "OFFBOARDPLAN_API_ALLOWED_DIRS"


class PlanRequest(BaseModel):
    sql_file: str | None = Field(
        None, description="Pipeline SQL file (whitelisted dirs)")
    sql_text: str = Field("", description="Inline pipeline SQL scripts")
    table: str = Field(..., description="The table to retire")
    grace_days: int = Field(30, description="Grace window in days")
    archive_db: str = Field("archive", description="Archive database")
    dialect: str = Field("hive", description="SQL dialect for the parser")
    llm: bool = Field(
        False, description="Also draft a retirement notice via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: PlanRequest, resolve):
    raw = resolve(req.sql_file, req.sql_text, "'sql_file' or 'sql_text'")
    return plan_offboard(raw, req.table, grace_days=req.grace_days,
                         archive_db=req.archive_db, dialect=req.dialect)


def _llm(req: PlanRequest, result, lang: str):
    from .advisor_llm import retirement_note
    from .i18n import tp

    note = retirement_note(result, lang=lang)
    return ("retirement_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/offboardplan", tags=["offboard_plan"],
    endpoint="plan", request_model=PlanRequest,
    health_name="offboard_plan", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
