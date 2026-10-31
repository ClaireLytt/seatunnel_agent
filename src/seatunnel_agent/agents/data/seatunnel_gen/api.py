"""REST API for the SeaTunnel job drafter — FastAPI router.

  POST /api/seatunnelgen/generate — linted job.conf draft
  GET  /api/seatunnelgen/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .generator import generate_config
from .report import render_markdown

_ENV = "SEATUNNELGEN_API_ALLOWED_DIRS"


class GenerateRequest(BaseModel):
    sql_file: str | None = Field(
        None, description="DDL file with the CREATE TABLE "
                          "(whitelisted dirs)")
    sql_text: str = Field("", description="Inline CREATE TABLE DDL")
    source: str = Field(..., description="Source connector, e.g. "
                                         "MySQL-CDC, Jdbc, Kafka")
    sink: str = Field(..., description="Sink connector, e.g. Doris, "
                                       "Hive, ClickHouse")
    job_mode: str = Field("", description="BATCH or STREAMING; empty = "
                                          "auto (CDC → STREAMING)")
    parallelism: int = Field(2, description="env.parallelism")
    dialect: str = Field("hive", description="SQL dialect for the parser")
    llm: bool = Field(
        False, description="Also draft a pre-run review via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: GenerateRequest, resolve):
    raw = resolve(req.sql_file, req.sql_text, "'sql_file' or 'sql_text'")
    return generate_config(raw, req.source, req.sink, dialect=req.dialect,
                           job_mode=req.job_mode,
                           parallelism=req.parallelism)


def _llm(req: GenerateRequest, result, lang: str):
    from .advisor_llm import job_note
    from .i18n import tp

    note = job_note(result, lang=lang)
    return ("job_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/seatunnelgen", tags=["seatunnel_gen"],
    endpoint="generate", request_model=GenerateRequest,
    health_name="seatunnel_gen", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
