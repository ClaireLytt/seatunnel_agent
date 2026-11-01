"""REST API for the cost allocator — FastAPI router.

  POST /api/costalloc/allocate — per-owner bill + graded findings
  GET  /api/costalloc/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .allocator import allocate_costs
from .report import render_markdown

_ENV = "COSTALLOC_API_ALLOWED_DIRS"


class AllocateRequest(BaseModel):
    data_file: str | None = Field(
        None, description="Usage inventory CSV/JSONL file "
                          "(whitelisted dirs)")
    data_text: str = Field("", description="Inline inventory: columns "
                                           "owner/item/storage_gb/"
                                           "compute_hours")
    storage_price: float = Field(0.02, description="Price per GB held")
    compute_price: float = Field(0.5, description="Price per compute hour")
    llm: bool = Field(
        False, description="Also draft a billing note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: AllocateRequest, resolve):
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    headers, rows = parse_rows(raw)
    return allocate_costs(headers, rows,
                          storage_price=req.storage_price,
                          compute_price=req.compute_price)


def _llm(req: AllocateRequest, result, lang: str):
    from .advisor_llm import billing_note
    from .i18n import tp

    note = billing_note(result, lang=lang)
    return ("billing_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/costalloc", tags=["cost_allocation"],
    endpoint="allocate", request_model=AllocateRequest,
    health_name="cost_allocation", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
