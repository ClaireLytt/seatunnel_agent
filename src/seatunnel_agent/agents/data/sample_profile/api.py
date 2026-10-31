"""REST API for the sample profiler — FastAPI router.

  POST /api/sampleprofile/profile — column profiles + findings
  GET  /api/sampleprofile/health  — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .profiler import parse_rows, profile_rows, sample_rows
from .report import render_markdown

_ENV = "SAMPLEPROFILE_API_ALLOWED_DIRS"


class ProfileRequest(BaseModel):
    data_file: str | None = Field(
        None, description="CSV/JSONL data file (whitelisted dirs)")
    data_text: str = Field("", description="Inline CSV or JSONL rows")
    max_rows: int = Field(
        2000, ge=1, le=100_000,
        description="Sample cap — deterministic stride sample above it")
    llm: bool = Field(
        False, description="Also draft a data-review note via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: ProfileRequest, resolve):
    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    headers, rows = parse_rows(raw)
    sampled = sample_rows(rows, req.max_rows)
    return profile_rows(headers, sampled, total_rows=len(rows))


def _llm(req: ProfileRequest, result, lang: str):
    from .advisor_llm import review_note
    from .i18n import tp

    note = review_note(result, lang=lang)
    return ("review_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/sampleprofile", tags=["sample_profile"],
    endpoint="profile", request_model=ProfileRequest,
    health_name="sample_profile", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
