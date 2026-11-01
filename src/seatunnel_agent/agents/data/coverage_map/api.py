"""REST API for the coverage mapper — FastAPI router.

  POST /api/coveragemap/map — per-table protection + graded findings
  GET  /api/coveragemap/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .mapper import map_coverage
from .report import render_markdown

_ENV = "COVERAGEMAP_API_ALLOWED_DIRS"


class MapRequest(BaseModel):
    ddl_file: str | None = Field(
        None, description="CREATE TABLE DDL file (whitelisted dirs)")
    ddl_text: str = Field("", description="Inline CREATE TABLE DDL")
    rules_text: str = Field("", description="DQC rules YAML (optional "
                                            "when a contract is given)")
    contract_text: str = Field("", description="Contract YAML (optional "
                                               "when rules are given)")
    dialect: str = Field("hive", description="SQL dialect for the parser")
    llm: bool = Field(
        False, description="Also draft a gap-closing plan via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: MapRequest, resolve):
    ddl = resolve(req.ddl_file, req.ddl_text, "'ddl_file' or 'ddl_text'")
    return map_coverage(ddl, rules_text=req.rules_text,
                        contract_text=req.contract_text,
                        dialect=req.dialect)


def _llm(req: MapRequest, result, lang: str):
    from .advisor_llm import coverage_note
    from .i18n import tp

    note = coverage_note(result, lang=lang)
    return ("coverage_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/coveragemap", tags=["coverage_map"],
    endpoint="map", request_model=MapRequest,
    health_name="coverage_map", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
