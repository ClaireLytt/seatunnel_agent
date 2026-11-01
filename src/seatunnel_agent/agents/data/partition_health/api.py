"""REST API for the partition-health analyzer — FastAPI router.

  POST /api/partitionhealth/check — gaps, empties, skew and surges
  GET  /api/partitionhealth/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .analyzer import analyze_partitions, parse_partition_listing
from .report import render_markdown

_ENV = "PARTITIONHEALTH_API_ALLOWED_DIRS"


class CheckRequest(BaseModel):
    listing_file: str | None = Field(
        None, description="Partition listing file (CSV or JSON list)")
    listing_text: str = Field("", description="Inline listing")
    llm: bool = Field(
        False, description="Also draft a partition note via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: CheckRequest, resolve):
    raw = resolve(req.listing_file, req.listing_text,
                  "'listing_file' or 'listing_text'")
    return analyze_partitions(parse_partition_listing(raw))


def _llm(req: CheckRequest, result, lang: str):
    from .advisor_llm import partition_note
    from .i18n import tp

    note = partition_note(result, lang=lang)
    return ("partition_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/partitionhealth", tags=["partition_health"],
    endpoint="check", request_model=CheckRequest,
    health_name="partition_health", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
