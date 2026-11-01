"""REST API for the Flink diagnoser — FastAPI router.

  POST /api/flinkdiag/diagnose — ranked job-health findings
  GET  /api/flinkdiag/health   — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .diagnoser import diagnose_job, parse_job_snapshot
from .report import render_markdown

_ENV = "FLINKDIAG_API_ALLOWED_DIRS"


class DiagnoseRequest(BaseModel):
    snapshot_file: str | None = Field(
        None, description="Job snapshot JSON file (whitelisted dirs)")
    snapshot_text: str = Field("", description="Inline snapshot JSON")
    llm: bool = Field(
        False, description="Also draft an ops note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: DiagnoseRequest, resolve):
    raw = resolve(req.snapshot_file, req.snapshot_text,
                  "'snapshot_file' or 'snapshot_text'")
    return diagnose_job(parse_job_snapshot(raw))


def _llm(req: DiagnoseRequest, diag, lang: str):
    from .advisor_llm import ops_note
    from .i18n import tp

    note = ops_note(diag, lang=lang)
    return ("ops_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/flinkdiag", tags=["flink_diag"],
    endpoint="diagnose", request_model=DiagnoseRequest,
    health_name="flink_diag", env_var=_ENV,
    core=_core,
    render=lambda diag, req, lang: render_markdown(diag, lang=lang),
    llm=_llm,
)
