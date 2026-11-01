"""REST API for the database diagnoser — FastAPI router.

  POST /api/dbdiag/diagnose — ranked runtime findings
  GET  /api/dbdiag/health   — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .diagnoser import diagnose_snapshot, parse_snapshot
from .report import render_markdown

_ENV = "DBDIAG_API_ALLOWED_DIRS"


class DiagnoseRequest(BaseModel):
    snapshot_file: str | None = Field(
        None, description="Status snapshot JSON file (whitelisted dirs)")
    snapshot_text: str = Field("", description="Inline snapshot JSON")
    llm: bool = Field(
        False, description="Also draft an incident note via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: DiagnoseRequest, resolve):
    raw = resolve(req.snapshot_file, req.snapshot_text,
                  "'snapshot_file' or 'snapshot_text'")
    return diagnose_snapshot(parse_snapshot(raw))


def _llm(req: DiagnoseRequest, diag, lang: str):
    from .advisor_llm import incident_note
    from .i18n import tp

    note = incident_note(diag, lang=lang)
    return ("incident_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/dbdiag", tags=["db_diag"],
    endpoint="diagnose", request_model=DiagnoseRequest,
    health_name="db_diag", env_var=_ENV,
    core=_core,
    render=lambda diag, req, lang: render_markdown(diag, lang=lang),
    llm=_llm,
)
