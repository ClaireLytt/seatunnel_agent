"""REST API for the realtime-latency analyzer — FastAPI router.

  POST /api/rtlatency/analyze — per-hop percentiles and outliers
  GET  /api/rtlatency/health  — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .analyzer import analyze_latency, parse_events
from .report import render_markdown

_ENV = "RTLATENCY_API_ALLOWED_DIRS"


class AnalyzeRequest(BaseModel):
    events_file: str | None = Field(
        None, description="Event timestamp rows file (CSV or JSONL)")
    events_text: str = Field("", description="Inline event rows")
    sla_ms: float = Field(0.0, ge=0,
                          description="End-to-end SLA in ms (0 = off)")
    llm: bool = Field(
        False, description="Also draft a latency note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: AnalyzeRequest, resolve):
    raw = resolve(req.events_file, req.events_text,
                  "'events_file' or 'events_text'")
    stages, events = parse_events(raw)
    return analyze_latency(stages, events, sla_ms=req.sla_ms)


def _llm(req: AnalyzeRequest, result, lang: str):
    from .advisor_llm import latency_note
    from .i18n import tp

    note = latency_note(result, lang=lang)
    return ("latency_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/rtlatency", tags=["rt_latency"],
    endpoint="analyze", request_model=AnalyzeRequest,
    health_name="rt_latency", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
