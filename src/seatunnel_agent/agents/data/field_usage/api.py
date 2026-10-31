"""REST API for the field-usage analyzer — FastAPI router.

  POST /api/fieldusage/analyze — per-column usage + graded findings
  GET  /api/fieldusage/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .analyzer import analyze_usage
from .report import render_markdown

_ENV = "FIELDUSAGE_API_ALLOWED_DIRS"


class AnalyzeRequest(BaseModel):
    ddl_file: str | None = Field(
        None, description="CREATE TABLE DDL file (whitelisted dirs)")
    ddl_text: str = Field("", description="Inline CREATE TABLE DDL")
    queries_file: str | None = Field(
        None, description="Query workload SQL file (whitelisted dirs)")
    queries_text: str = Field("", description="Inline query workload")
    dialect: str = Field("hive", description="SQL dialect for the parser")
    llm: bool = Field(
        False, description="Also draft disposition advice via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: AnalyzeRequest, resolve):
    ddl = resolve(req.ddl_file, req.ddl_text, "'ddl_file' or 'ddl_text'")
    queries = resolve(req.queries_file, req.queries_text,
                      "'queries_file' or 'queries_text'")
    return analyze_usage(ddl, queries, dialect=req.dialect)


def _llm(req: AnalyzeRequest, result, lang: str):
    from .advisor_llm import usage_note
    from .i18n import tp

    note = usage_note(result, lang=lang)
    return ("usage_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/fieldusage", tags=["field_usage"],
    endpoint="analyze", request_model=AnalyzeRequest,
    health_name="field_usage", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
