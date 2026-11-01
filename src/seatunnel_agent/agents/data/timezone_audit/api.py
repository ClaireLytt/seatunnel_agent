"""REST API for the timezone auditor — FastAPI router.

  POST /api/timezoneaudit/audit — per-column findings
  GET  /api/timezoneaudit/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .auditor import audit_timezones
from .report import render_markdown

_ENV = "TIMEZONEAUDIT_API_ALLOWED_DIRS"


class AuditRequest(BaseModel):
    data_file: str | None = Field(
        None, description="Data rows CSV/JSONL file (whitelisted dirs)")
    data_text: str = Field("", description="Inline rows with timestamp "
                                           "columns")
    llm: bool = Field(
        False, description="Also draft a normalization plan via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: AuditRequest, resolve):
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    headers, rows = parse_rows(raw)
    return audit_timezones(headers, rows)


def _llm(req: AuditRequest, result, lang: str):
    from .advisor_llm import normalization_note
    from .i18n import tp

    note = normalization_note(result, lang=lang)
    return ("normalization_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/timezoneaudit", tags=["timezone_audit"],
    endpoint="audit", request_model=AuditRequest,
    health_name="timezone_audit", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
