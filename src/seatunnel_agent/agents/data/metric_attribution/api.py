"""REST API for the metric attributor — FastAPI router.

  POST /api/metricattribution/attribute — additive decomposition
  GET  /api/metricattribution/health    — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .attributor import attribute_change
from .report import render_markdown

_ENV = "METRICATTRIBUTION_API_ALLOWED_DIRS"


class AttributeRequest(BaseModel):
    baseline_file: str | None = Field(
        None, description="Baseline result rows file (CSV/JSONL)")
    baseline_text: str = Field("", description="Inline baseline rows")
    current_file: str | None = Field(
        None, description="Current result rows file (CSV/JSONL)")
    current_text: str = Field("", description="Inline current rows")
    dims: str = Field(..., description="Dimension column(s), "
                                       "comma-separated")
    metric: str = Field(..., description="Metric column to attribute")
    llm: bool = Field(
        False, description="Also draft an attribution reply via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: AttributeRequest, resolve):
    base = resolve(req.baseline_file, req.baseline_text,
                   "'baseline_file' or 'baseline_text'")
    cur = resolve(req.current_file, req.current_text,
                  "'current_file' or 'current_text'")
    return attribute_change(base, cur, req.dims, req.metric)


def _llm(req: AttributeRequest, result, lang: str):
    from .advisor_llm import attribution_note
    from .i18n import tp

    note = attribution_note(result, lang=lang)
    return ("attribution_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/metricattribution", tags=["metric_attribution"],
    endpoint="attribute", request_model=AttributeRequest,
    health_name="metric_attribution", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
