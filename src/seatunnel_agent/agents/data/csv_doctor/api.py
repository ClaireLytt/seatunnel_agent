"""REST API for the CSV doctor — FastAPI router.

  POST /api/csvdoctor/diagnose — diagnosis + repaired CSV
  GET  /api/csvdoctor/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .doctor import diagnose_csv
from .report import render_markdown

_ENV = "CSVDOCTOR_API_ALLOWED_DIRS"


class DiagnoseRequest(BaseModel):
    data_file: str | None = Field(
        None, description="Broken CSV file (whitelisted dirs)")
    data_text: str = Field("", description="Inline raw CSV text")
    llm: bool = Field(
        False, description="Also draft an incident note via the "
                           "configured LLM (needs an API key; finding "
                           "metadata only, never the rows)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: DiagnoseRequest, resolve):
    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    return diagnose_csv(raw)


def _llm(req: DiagnoseRequest, result, lang: str):
    from .advisor_llm import incident_note
    from .i18n import tp

    note = incident_note(result, lang=lang)
    return ("incident_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/csvdoctor", tags=["csv_doctor"],
    endpoint="diagnose", request_model=DiagnoseRequest,
    health_name="csv_doctor", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
