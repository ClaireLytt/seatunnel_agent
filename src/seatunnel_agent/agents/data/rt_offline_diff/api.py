"""REST API for the realtime-offline reconciler — FastAPI router.

  POST /api/rtoffline/compare — key-aligned diff with bias verdicts
  GET  /api/rtoffline/health  — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .comparator import compare_results
from .report import render_markdown

_ENV = "RTOFFLINE_API_ALLOWED_DIRS"


class CompareRequest(BaseModel):
    realtime_file: str | None = Field(
        None, description="Realtime result rows file (CSV/JSONL)")
    realtime_text: str = Field("", description="Inline realtime rows")
    offline_file: str | None = Field(
        None, description="Offline result rows file (CSV/JSONL)")
    offline_text: str = Field("", description="Inline offline rows")
    keys: str = Field(..., description="Key column(s), comma-separated")
    tolerance_pct: float = Field(1.0, ge=0,
                                 description="Relative tolerance in %")
    llm: bool = Field(
        False, description="Also draft a reconciliation note via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: CompareRequest, resolve):
    rt_raw = resolve(req.realtime_file, req.realtime_text,
                     "'realtime_file' or 'realtime_text'")
    off_raw = resolve(req.offline_file, req.offline_text,
                      "'offline_file' or 'offline_text'")
    return compare_results(rt_raw, off_raw, req.keys,
                           tolerance_pct=req.tolerance_pct)


def _llm(req: CompareRequest, result, lang: str):
    from .advisor_llm import recon_note
    from .i18n import tp

    note = recon_note(result, lang=lang)
    return ("recon_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/rtoffline", tags=["rt_offline_diff"],
    endpoint="compare", request_model=CompareRequest,
    health_name="rt_offline_diff", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
