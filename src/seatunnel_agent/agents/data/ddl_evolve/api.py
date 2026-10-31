"""REST API for the DDL evolver — FastAPI router.

  POST /api/ddlevolve/migrate — migration steps + paste-ready script
  GET  /api/ddlevolve/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .evolver import build_migration
from .report import render_markdown

_ENV = "DDLEVOLVE_API_ALLOWED_DIRS"


class MigrateRequest(BaseModel):
    old_file: str | None = Field(
        None, description="Old DDL snapshot file (whitelisted dirs)")
    old_text: str = Field("", description="Inline old CREATE TABLE DDL")
    new_file: str | None = Field(
        None, description="New DDL snapshot file (whitelisted dirs)")
    new_text: str = Field("", description="Inline new CREATE TABLE DDL")
    dialect: str = Field("hive", description="Target dialect: hive|mysql")
    llm: bool = Field(
        False, description="Also draft rollout advice via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: MigrateRequest, resolve):
    old = resolve(req.old_file, req.old_text, "'old_file' or 'old_text'")
    new = resolve(req.new_file, req.new_text, "'new_file' or 'new_text'")
    return build_migration(old, new, dialect=req.dialect)


def _llm(req: MigrateRequest, result, lang: str):
    from .advisor_llm import migration_note
    from .i18n import tp

    note = migration_note(result, lang=lang)
    return ("migration_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/ddlevolve", tags=["ddl_evolve"],
    endpoint="migrate", request_model=MigrateRequest,
    health_name="ddl_evolve", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
