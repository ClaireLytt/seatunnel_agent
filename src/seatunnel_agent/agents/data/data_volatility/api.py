"""REST API for the data-volatility analyzer — FastAPI router.

  POST /api/datavolatility/analyze — surges, drops, shifts, flatlines
  GET  /api/datavolatility/health  — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .analyzer import analyze_series, parse_series
from .report import render_markdown

_ENV = "DATAVOLATILITY_API_ALLOWED_DIRS"


class AnalyzeRequest(BaseModel):
    series_file: str | None = Field(
        None, description="CSV/JSONL series file: date,metric,value rows")
    series_text: str = Field("", description="Inline series rows")
    llm: bool = Field(
        False, description="Also draft a volatility note via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: AnalyzeRequest, resolve):
    raw = resolve(req.series_file, req.series_text,
                  "'series_file' or 'series_text'")
    return analyze_series(parse_series(raw))


def _llm(req: AnalyzeRequest, result, lang: str):
    from .advisor_llm import volatility_note
    from .i18n import tp

    note = volatility_note(result, lang=lang)
    return ("volatility_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/datavolatility", tags=["data_volatility"],
    endpoint="analyze", request_model=AnalyzeRequest,
    health_name="data_volatility", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
