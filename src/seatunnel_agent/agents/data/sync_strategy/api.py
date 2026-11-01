"""REST API for the sync-strategy agent — FastAPI router.

  POST /api/syncstrategy/recommend — per-table strategy with reasons
  GET  /api/syncstrategy/health    — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .advisor import parse_tables, recommend
from .report import render_markdown

_ENV = "SYNCSTRATEGY_API_ALLOWED_DIRS"


class RecommendRequest(BaseModel):
    file: str | None = Field(
        None, description="Table characteristics inventory (.json/.csv)")
    text: str | None = Field(None, description="Inline JSON/CSV inventory")
    llm: bool = Field(
        False, description="Also write the rollout narrative via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _llm(req: RecommendRequest, result, lang: str):
    from .advisor_llm import rollout_narrative
    from .i18n import tp

    narrative = rollout_narrative(result, lang=lang)
    return ("rollout_narrative", narrative,
            f"### {tp(lang, 'rpt_rollout')}\n{narrative}\n")


router = make_text_router(
    prefix="/api/syncstrategy", tags=["sync_strategy"],
    endpoint="recommend", request_model=RecommendRequest,
    health_name="sync_strategy", env_var=_ENV,
    core=lambda req, resolve: recommend(
        parse_tables(resolve(req.file, req.text, "'file' or 'text'"))),
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
