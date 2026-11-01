"""REST API for the capacity forecaster — FastAPI router.

  POST /api/capacityforecast/forecast — exhaustion date and top growers
  GET  /api/capacityforecast/health   — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .forecaster import forecast_capacity
from .report import render_markdown

_ENV = "CAPACITYFORECAST_API_ALLOWED_DIRS"


class ForecastRequest(BaseModel):
    series_file: str | None = Field(
        None, description="Storage series file: date,metric,value rows")
    series_text: str = Field("", description="Inline series rows")
    quota: float = Field(..., gt=0,
                         description="Capacity quota (same unit as the "
                                     "values, GB or rows)")
    window: int = Field(14, ge=2,
                        description="Points in the slope window")
    llm: bool = Field(
        False, description="Also draft a capacity note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: ForecastRequest, resolve):
    raw = resolve(req.series_file, req.series_text,
                  "'series_file' or 'series_text'")
    return forecast_capacity(raw, quota=req.quota, window=req.window)


def _llm(req: ForecastRequest, result, lang: str):
    from .advisor_llm import capacity_note
    from .i18n import tp

    note = capacity_note(result, lang=lang)
    return ("capacity_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/capacityforecast", tags=["capacity_forecast"],
    endpoint="forecast", request_model=ForecastRequest,
    health_name="capacity_forecast", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
