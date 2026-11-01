"""REST API for the compaction planner — FastAPI router.

  POST /api/compactplan/plan — ranked merge candidates + templates
  GET  /api/compactplan/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .planner import plan_compaction
from .report import render_markdown

_ENV = "COMPACTPLAN_API_ALLOWED_DIRS"


class PlanRequest(BaseModel):
    data_file: str | None = Field(
        None, description="File inventory CSV/JSONL file "
                          "(whitelisted dirs)")
    data_text: str = Field("", description="Inline inventory: columns "
                                           "table/partition/file_count/"
                                           "total_mb")
    small_mb: float = Field(32.0, description="Average file size below "
                                              "this marks small files")
    target_mb: float = Field(256.0, description="Target file size after "
                                                "the merge")
    llm: bool = Field(
        False, description="Also draft an execution review via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: PlanRequest, resolve):
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    headers, rows = parse_rows(raw)
    return plan_compaction(headers, rows, small_mb=req.small_mb,
                           target_mb=req.target_mb)


def _llm(req: PlanRequest, result, lang: str):
    from .advisor_llm import compaction_note
    from .i18n import tp

    note = compaction_note(result, lang=lang)
    return ("compaction_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/compactplan", tags=["compact_plan"],
    endpoint="plan", request_model=PlanRequest,
    health_name="compact_plan", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
