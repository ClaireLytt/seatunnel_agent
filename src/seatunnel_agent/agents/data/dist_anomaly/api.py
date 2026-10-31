"""REST API for the distribution-anomaly comparator — FastAPI router.

  POST /api/distanomaly/compare — drift findings between two samples
  GET  /api/distanomaly/health  — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .comparator import compare_profiles, load_profile
from .report import render_markdown

_ENV = "DISTANOMALY_API_ALLOWED_DIRS"


class CompareRequest(BaseModel):
    baseline_file: str | None = Field(
        None, description="Baseline CSV/JSONL rows or profile JSON file")
    baseline_text: str = Field("", description="Inline baseline input")
    current_file: str | None = Field(
        None, description="Current CSV/JSONL rows or profile JSON file")
    current_text: str = Field("", description="Inline current input")
    max_rows: int = Field(
        2000, ge=1, le=100_000,
        description="Sample cap per side when profiling raw rows")
    llm: bool = Field(
        False, description="Also draft a drift note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: CompareRequest, resolve):
    base_raw = resolve(req.baseline_file, req.baseline_text,
                       "'baseline_file' or 'baseline_text'")
    cur_raw = resolve(req.current_file, req.current_text,
                      "'current_file' or 'current_text'")
    return compare_profiles(load_profile(base_raw, req.max_rows),
                            load_profile(cur_raw, req.max_rows))


def _llm(req: CompareRequest, result, lang: str):
    from .advisor_llm import drift_note
    from .i18n import tp

    note = drift_note(result, lang=lang)
    return ("drift_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/distanomaly", tags=["dist_anomaly"],
    endpoint="compare", request_model=CompareRequest,
    health_name="dist_anomaly", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
