"""REST API for the contract generator — FastAPI router.

  POST /api/contractgen/generate — DDL → contract YAML draft
  GET  /api/contractgen/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .generator import generate_contract
from .report import render_markdown

_ENV = "CONTRACTGEN_API_ALLOWED_DIRS"


class GenerateRequest(BaseModel):
    sql_file: str | None = Field(
        None, description="DDL file with CREATE TABLE statements "
                          "(whitelisted dirs)")
    sql_text: str = Field("", description="Inline CREATE TABLE DDL")
    tables: list[str] = Field(
        default_factory=list,
        description="Restrict the draft to these tables (all when empty)")
    with_types: bool = Field(True, description="Pin column types")
    comment_threshold: float = Field(
        0.8, description="Coverage at or above this sets "
                         "require_comments: true")
    allow_extra: bool = Field(
        True, description="allow_extra_columns in the draft")
    dialect: str = Field("hive", description="SQL dialect for the parser")
    llm: bool = Field(
        False, description="Also draft tightening suggestions via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: GenerateRequest, resolve):
    raw = resolve(req.sql_file, req.sql_text, "'sql_file' or 'sql_text'")
    return generate_contract(raw, dialect=req.dialect,
                             with_types=req.with_types,
                             comment_threshold=req.comment_threshold,
                             allow_extra=req.allow_extra,
                             tables=req.tables or None)


def _llm(req: GenerateRequest, draft, lang: str):
    from .advisor_llm import tighten_note
    from .i18n import tp

    note = tighten_note(draft, lang=lang)
    return ("tighten_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/contractgen", tags=["contract_gen"],
    endpoint="generate", request_model=GenerateRequest,
    health_name="contract_gen", env_var=_ENV,
    core=_core,
    render=lambda draft, req, lang: render_markdown(draft, lang=lang),
    llm=_llm,
)
