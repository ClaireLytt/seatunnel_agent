"""REST API for the duplicate checker — FastAPI router.

  POST /api/dupcheck/check  — duplicate groups across three layers
  GET  /api/dupcheck/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .detector import detect_dups
from .report import render_markdown

_ENV = "DUPCHECK_API_ALLOWED_DIRS"


class CheckRequest(BaseModel):
    data_file: str | None = Field(
        None, description="CSV/JSONL data file (whitelisted dirs)")
    data_text: str = Field("", description="Inline CSV or JSONL rows")
    pk: str = Field("", description="Primary-key column(s), comma-separated")
    biz_key: str = Field(
        "", description="Business-event key column(s), comma-separated")
    llm: bool = Field(
        False, description="Also draft a dedup note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: CheckRequest, resolve):
    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    return detect_dups(raw, pk=req.pk or None, biz_key=req.biz_key or None)


def _llm(req: CheckRequest, result, lang: str):
    from .advisor_llm import dedup_note
    from .i18n import tp

    note = dedup_note(result, lang=lang)
    return ("dedup_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/dupcheck", tags=["dup_check"],
    endpoint="check", request_model=CheckRequest,
    health_name="dup_check", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
