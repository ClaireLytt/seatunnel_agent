"""REST API for the DQC rule drafter — FastAPI router.

  POST /api/dqrulegen/generate — loadable rules.yaml draft
  GET  /api/dqrulegen/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .generator import generate_rules
from .report import render_markdown

_ENV = "DQRULEGEN_API_ALLOWED_DIRS"


class GenerateRequest(BaseModel):
    data_file: str | None = Field(
        None, description="Sample CSV/JSONL file (whitelisted dirs)")
    data_text: str = Field("", description="Inline sample rows: CSV with "
                                           "a header, or JSONL")
    table: str = Field(..., description="Table name the rules gate")
    where: str = Field("", description="Optional partition filter, e.g. "
                                       "dt = '${yesterday_pt}'")
    max_change_pct: float = Field(
        50.0, description="row_count change guard vs the last run")
    llm: bool = Field(
        False, description="Also draft tightening suggestions via the "
                           "configured LLM (needs an API key; check "
                           "metadata only, never the rows)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: GenerateRequest, resolve):
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    headers, rows = parse_rows(raw)
    return generate_rules(headers, rows, req.table, where=req.where,
                          max_change_pct=req.max_change_pct)


def _llm(req: GenerateRequest, result, lang: str):
    from .advisor_llm import tighten_note
    from .i18n import tp

    note = tighten_note(result, lang=lang)
    return ("tighten_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/dqrulegen", tags=["dq_rulegen"],
    endpoint="generate", request_model=GenerateRequest,
    health_name="dq_rulegen", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
