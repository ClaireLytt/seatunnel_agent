"""REST API for the rollback planner — FastAPI router.

  POST /api/rollbackplan/plan — leveled restore + re-run steps
  GET  /api/rollbackplan/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .planner import plan_rollback
from .report import render_markdown

_ENV = "ROLLBACKPLAN_API_ALLOWED_DIRS"


class PlanRequest(BaseModel):
    sql_file: str | None = Field(
        None, description="Pipeline SQL file (whitelisted dirs)")
    sql_text: str = Field("", description="Inline pipeline SQL scripts")
    table: str = Field(..., description="The badly-loaded table")
    partitions: list[str] = Field(
        default_factory=list, description="Bad partitions, e.g. "
                                          "['dt=2026-10-30']")
    mode: str = Field("rerun",
                      description="Restore mode: snapshot|rerun|overwrite")
    snapshot: str = Field("", description="Snapshot table for mode "
                                          "'snapshot'")
    durations: dict[str, float] = Field(
        default_factory=dict,
        description="Optional per-table re-run minutes for the estimate")
    dialect: str = Field("hive", description="SQL dialect for the parser")
    llm: bool = Field(
        False, description="Also draft an incident update via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: PlanRequest, resolve):
    raw = resolve(req.sql_file, req.sql_text, "'sql_file' or 'sql_text'")
    if not req.table.strip():
        raise ValueError("'table' must not be empty")
    return plan_rollback(raw, req.table, partitions=req.partitions,
                         mode=req.mode, snapshot=req.snapshot,
                         durations=req.durations, dialect=req.dialect)


def _llm(req: PlanRequest, plan, lang: str):
    from .advisor_llm import rollback_note
    from .i18n import tp

    note = rollback_note(plan, lang=lang)
    return ("rollback_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/rollbackplan", tags=["rollback_plan"],
    endpoint="plan", request_model=PlanRequest,
    health_name="rollback_plan", env_var=_ENV,
    core=_core,
    render=lambda plan, req, lang: render_markdown(plan, lang=lang),
    llm=_llm,
)
