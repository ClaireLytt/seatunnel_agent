"""REST API for the SLA board — FastAPI router.

  POST /api/slaboard/score — per-task attainment + graded findings
  GET  /api/slaboard/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .board import build_board
from .report import render_markdown

_ENV = "SLABOARD_API_ALLOWED_DIRS"


class ScoreRequest(BaseModel):
    data_file: str | None = Field(
        None, description="Completion records CSV/JSONL file "
                          "(whitelisted dirs)")
    data_text: str = Field("", description="Inline records with columns "
                                           "task/date/deadline/finish")
    target: float = Field(0.95, description="Attainment target (0.5..1)")
    llm: bool = Field(
        False, description="Also draft an SLA update via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: ScoreRequest, resolve):
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    headers, rows = parse_rows(raw)
    return build_board(headers, rows, target=req.target)


def _llm(req: ScoreRequest, result, lang: str):
    from .advisor_llm import sla_note
    from .i18n import tp

    note = sla_note(result, lang=lang)
    return ("sla_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/slaboard", tags=["sla_board"],
    endpoint="score", request_model=ScoreRequest,
    health_name="sla_board", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
