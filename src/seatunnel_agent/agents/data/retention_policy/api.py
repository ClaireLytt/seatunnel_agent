"""REST API for the retention advisor — FastAPI router.

  POST /api/retention/advise — per-table TTL advice + graded findings
  GET  /api/retention/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .advisor import advise_retention
from .report import render_markdown

_ENV = "RETENTION_API_ALLOWED_DIRS"


class AdviseRequest(BaseModel):
    data_file: str | None = Field(
        None, description="Partition inventory CSV/JSONL file "
                          "(whitelisted dirs)")
    data_text: str = Field("", description="Inline inventory: columns "
                                           "table/partition/size_gb/"
                                           "last_access")
    active_days: int = Field(90, description="A read inside this window "
                                             "keeps a partition warm")
    llm: bool = Field(
        False, description="Also draft a cleanup proposal via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: AdviseRequest, resolve):
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    headers, rows = parse_rows(raw)
    return advise_retention(headers, rows, active_days=req.active_days)


def _llm(req: AdviseRequest, result, lang: str):
    from .advisor_llm import retention_note
    from .i18n import tp

    note = retention_note(result, lang=lang)
    return ("retention_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/retention", tags=["retention_policy"],
    endpoint="advise", request_model=AdviseRequest,
    health_name="retention_policy", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
