"""REST API for the slow-query diagnoser — FastAPI router.

  POST /api/slowquery/diagnose — ranked root causes with prescriptions
  GET  /api/slowquery/health   — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .diagnoser import diagnose, parse_baseline, parse_metrics
from .report import render_markdown

_ENV = "SLOWQUERY_API_ALLOWED_DIRS"


class DiagnoseRequest(BaseModel):
    metrics: str = Field(..., description="One run's metrics JSON")
    baseline_file: str | None = Field(
        None, description="History baseline jsonl file")
    baseline_text: str = Field("", description="Inline baseline jsonl")
    llm: bool = Field(
        False, description="Also draft an ops-channel note via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: DiagnoseRequest, resolve):
    if not req.metrics.strip():
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Provide 'metrics'")
    baseline_raw = ""
    if (req.baseline_file or "").strip() or req.baseline_text.strip():
        baseline_raw = resolve(req.baseline_file, req.baseline_text,
                               "'baseline_file' or 'baseline_text'")
    return diagnose(parse_metrics(req.metrics), parse_baseline(baseline_raw))


def _llm(req: DiagnoseRequest, diag, lang: str):
    from .advisor_llm import incident_note
    from .i18n import tp

    note = incident_note(diag, lang=lang)
    return ("incident_note", note,
            f"### {tp(lang, 'rpt_incident_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/slowquery", tags=["slow_query"],
    endpoint="diagnose", request_model=DiagnoseRequest,
    health_name="slow_query", env_var=_ENV,
    core=_core,
    render=lambda diag, req, lang: render_markdown(diag, lang=lang),
    llm=_llm,
)
