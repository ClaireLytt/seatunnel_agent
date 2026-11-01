"""REST API for the alert-storm analyzer — FastAPI router.

  POST /api/alertstorm/digest — clusters, storms and suppression hints
  GET  /api/alertstorm/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .analyzer import analyze_alerts, parse_alerts
from .report import render_markdown

_ENV = "ALERTSTORM_API_ALLOWED_DIRS"


class DigestRequest(BaseModel):
    export_file: str | None = Field(
        None, description="Alert export file (CSV or JSON list)")
    export_text: str = Field("", description="Inline export")
    llm: bool = Field(
        False, description="Also draft a handover digest via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: DigestRequest, resolve):
    raw = resolve(req.export_file, req.export_text,
                  "'export_file' or 'export_text'")
    return analyze_alerts(parse_alerts(raw))


def _llm(req: DigestRequest, result, lang: str):
    from .advisor_llm import digest_note
    from .i18n import tp

    note = digest_note(result, lang=lang)
    return ("digest_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/alertstorm", tags=["alert_storm"],
    endpoint="digest", request_model=DigestRequest,
    health_name="alert_storm", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
