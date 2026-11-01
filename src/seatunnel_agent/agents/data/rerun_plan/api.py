"""REST API for the rerun planner agent — FastAPI router.

  POST /api/rerun/plan   — minimal rerun set in topological batches
  GET  /api/rerun/health — health check
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .planner import parse_dag, parse_statuses, plan_rerun
from .report import render_markdown

_ENV = "RERUN_API_ALLOWED_DIRS"


class PlanRequest(BaseModel):
    file: str | None = Field(
        None, description="Task DAG file (.json or text lines)")
    text: str | None = Field(None, description="Inline DAG definition")
    failed: str = Field("", description="Failed task names, comma-separated")
    succeeded: str = Field(
        "", description="Already-succeeded task names, comma-separated")
    statuses: str = Field(
        "", description="Scheduler status export: {'task':'state'} JSON or "
                        "task=state lines (overrides failed/succeeded)")
    cmd: str = Field("", description="Command template with {task}")
    llm: bool = Field(
        False, description="Also draft an incident note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: PlanRequest, resolve):
    text = resolve(req.file, req.text, "'file' or 'text'")
    if not req.failed.strip() and not req.statuses.strip():
        raise HTTPException(status_code=400,
                            detail="Provide 'failed' or 'statuses'")
    failed: str | list[str] = req.failed
    succeeded: str | list[str] = req.succeeded
    if req.statuses.strip():
        failed, succeeded = parse_statuses(req.statuses)
    return plan_rerun(parse_dag(text), failed, succeeded)


def _llm(req: PlanRequest, result, lang: str):
    from .advisor_llm import incident_note
    from .i18n import tp

    note = incident_note(result, lang=lang)
    return ("incident_note", note,
            f"### {tp(lang, 'rpt_incident_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/rerun", tags=["rerun_plan"],
    endpoint="plan", request_model=PlanRequest,
    health_name="rerun_plan", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(
        result, lang=lang, cmd_template=req.cmd),
    llm=_llm,
)
