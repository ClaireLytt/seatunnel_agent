"""REST API for the duplicate-pipeline detector — FastAPI router.

  POST /api/duppipeline/detect — graded duplicate-build findings
  GET  /api/duppipeline/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .detector import detect_dup_pipelines
from .report import render_markdown

_ENV = "DUPPIPELINE_API_ALLOWED_DIRS"


class DetectRequest(BaseModel):
    sql_file: str | None = Field(
        None, description="Pipeline SQL file (whitelisted dirs)")
    sql_text: str = Field("", description="Inline pipeline SQL scripts")
    fanout: int = Field(3, description="Direct readers at or above this "
                                       "flag DP003")
    dialect: str = Field("hive", description="SQL dialect for the parser")
    llm: bool = Field(
        False, description="Also draft a consolidation plan via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: DetectRequest, resolve):
    raw = resolve(req.sql_file, req.sql_text, "'sql_file' or 'sql_text'")
    return detect_dup_pipelines(raw, dialect=req.dialect, fanout=req.fanout)


def _llm(req: DetectRequest, result, lang: str):
    from .advisor_llm import consolidation_note
    from .i18n import tp

    note = consolidation_note(result, lang=lang)
    return ("consolidation_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/duppipeline", tags=["dup_pipeline"],
    endpoint="detect", request_model=DetectRequest,
    health_name="dup_pipeline", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
