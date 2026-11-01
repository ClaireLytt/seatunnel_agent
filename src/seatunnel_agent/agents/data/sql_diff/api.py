"""REST API for the SQL semantic differ — FastAPI router.

  POST /api/sqldiff/diff — graded semantic differences
  GET  /api/sqldiff/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .differ import diff_sql
from .report import render_markdown

_ENV = "SQLDIFF_API_ALLOWED_DIRS"


class DiffRequest(BaseModel):
    old_file: str | None = Field(
        None, description="Old SQL file (whitelisted dirs)")
    old_text: str = Field("", description="Inline old SQL")
    new_file: str | None = Field(
        None, description="New SQL file (whitelisted dirs)")
    new_text: str = Field("", description="Inline new SQL")
    dialect: str = Field("hive", description="SQL dialect for the parser")
    llm: bool = Field(
        False, description="Also draft a change review via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: DiffRequest, resolve):
    old = resolve(req.old_file, req.old_text, "'old_file' or 'old_text'")
    new = resolve(req.new_file, req.new_text, "'new_file' or 'new_text'")
    return diff_sql(old, new, dialect=req.dialect)


def _llm(req: DiffRequest, result, lang: str):
    from .advisor_llm import change_note
    from .i18n import tp

    note = change_note(result, lang=lang)
    return ("change_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/sqldiff", tags=["sql_diff"],
    endpoint="diff", request_model=DiffRequest,
    health_name="sql_diff", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
