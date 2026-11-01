"""REST API for the schema-to-DDL converter — FastAPI router.

  POST /api/avro2ddl/convert — column mapping + CREATE TABLE draft
  GET  /api/avro2ddl/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .converter import convert_schema
from .report import render_markdown

_ENV = "AVRO2DDL_API_ALLOWED_DIRS"


class ConvertRequest(BaseModel):
    schema_file: str | None = Field(
        None, description="Schema JSON file (whitelisted dirs)")
    schema_text: str = Field("", description="Inline Avro record or "
                                             "JSON Schema")
    table: str = Field("", description="Target table name (defaults to "
                                       "the record's namespace.name)")
    dialect: str = Field("hive", description="Target dialect: hive|doris")
    llm: bool = Field(
        False, description="Also draft a landing review via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: ConvertRequest, resolve):
    raw = resolve(req.schema_file, req.schema_text,
                  "'schema_file' or 'schema_text'")
    return convert_schema(raw, table=req.table, dialect=req.dialect)


def _llm(req: ConvertRequest, result, lang: str):
    from .advisor_llm import landing_note
    from .i18n import tp

    note = landing_note(result, lang=lang)
    return ("landing_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/avro2ddl", tags=["avro2ddl"],
    endpoint="convert", request_model=ConvertRequest,
    health_name="avro2ddl", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
