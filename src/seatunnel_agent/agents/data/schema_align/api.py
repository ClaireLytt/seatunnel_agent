"""REST API for the schema aligner — FastAPI router.

  POST /api/schemaalign/align — graded mapping risks
  GET  /api/schemaalign/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .aligner import align_schemas
from .report import render_markdown

_ENV = "SCHEMAALIGN_API_ALLOWED_DIRS"


class AlignRequest(BaseModel):
    source_file: str | None = Field(
        None, description="Source table DDL file (whitelisted dirs)")
    source_text: str = Field("", description="Inline source DDL")
    sink_file: str | None = Field(
        None, description="Sink table DDL file (whitelisted dirs)")
    sink_text: str = Field("", description="Inline sink DDL")
    llm: bool = Field(
        False, description="Also draft an alignment review via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: AlignRequest, resolve):
    src = resolve(req.source_file, req.source_text,
                  "'source_file' or 'source_text'")
    dst = resolve(req.sink_file, req.sink_text,
                  "'sink_file' or 'sink_text'")
    return align_schemas(src, dst)


def _llm(req: AlignRequest, result, lang: str):
    from .advisor_llm import alignment_note
    from .i18n import tp

    note = alignment_note(result, lang=lang)
    return ("alignment_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/schemaalign", tags=["schema_align"],
    endpoint="align", request_model=AlignRequest,
    health_name="schema_align", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
