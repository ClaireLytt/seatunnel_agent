"""REST API for the data-dictionary generator — FastAPI router.

  POST /api/datadict/generate — dictionary skeleton per table
  GET  /api/datadict/health   — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .generator import generate_dict
from .report import render_markdown

_ENV = "DATADICT_API_ALLOWED_DIRS"


class GenerateRequest(BaseModel):
    catalog_file: str | None = Field(
        None, description="Catalog file: JSON asset list or DDL scripts")
    catalog_text: str = Field("", description="Inline catalog")
    sql_text: str = Field(
        "", description="Optional SQL workload for usage mining")
    llm: bool = Field(
        False, description="Also draft business descriptions for "
                           "uncommented columns via the configured LLM")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: GenerateRequest, resolve):
    raw = resolve(req.catalog_file, req.catalog_text,
                  "'catalog_file' or 'catalog_text'")
    return generate_dict(raw, sql_text=req.sql_text)


def _llm(req: GenerateRequest, result, lang: str):
    from .advisor_llm import describe_columns
    from .i18n import tp

    note = describe_columns(result, lang=lang)
    return ("descriptions", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/datadict", tags=["data_dict"],
    endpoint="generate", request_model=GenerateRequest,
    health_name="data_dict", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
