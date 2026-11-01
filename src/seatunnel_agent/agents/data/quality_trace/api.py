"""REST API for the quality root-cause tracer — FastAPI router.

  POST /api/qualitytrace/trace — ranked upstream suspects
  GET  /api/qualitytrace/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .report import render_markdown
from .tracer import build_graph_from_sql, trace_quality

_ENV = "QUALITYTRACE_API_ALLOWED_DIRS"


class TraceRequest(BaseModel):
    sql_file: str | None = Field(
        None, description="Pipeline SQL file (whitelisted dirs)")
    sql_text: str = Field("", description="Inline pipeline SQL scripts")
    table: str = Field(..., description="Polluted table name")
    column: str = Field("", description="Polluted column (optional)")
    symptom: str = Field("", description="One-line symptom (optional)")
    dialect: str = Field("hive", description="SQL dialect for the parser")
    llm: bool = Field(
        False, description="Also draft a trace note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: TraceRequest, resolve):
    raw = resolve(req.sql_file, req.sql_text, "'sql_file' or 'sql_text'")
    if not req.table.strip():
        raise ValueError("'table' must not be empty")
    graph, warnings = build_graph_from_sql(raw, dialect=req.dialect)
    return trace_quality(graph, warnings, req.table,
                         column=req.column, symptom=req.symptom)


def _llm(req: TraceRequest, result, lang: str):
    from .advisor_llm import trace_note
    from .i18n import tp

    note = trace_note(result, lang=lang)
    return ("trace_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/qualitytrace", tags=["quality_trace"],
    endpoint="trace", request_model=TraceRequest,
    health_name="quality_trace", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
