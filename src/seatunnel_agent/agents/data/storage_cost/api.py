"""REST API for the storage-cost analyzer — FastAPI router.

  POST /api/storagecost/analyze — ranked reclaim actions
  GET  /api/storagecost/health  — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .analyzer import run_storage_analysis
from .report import render_markdown

_ENV = "STORAGECOST_API_ALLOWED_DIRS"


class AnalyzeRequest(BaseModel):
    inventory_file: str | None = Field(
        None, description="Inventory file: CSV or JSON asset rows "
                          "(optional avg_file_mb column)")
    inventory_text: str = Field("", description="Inline inventory rows")
    partitions_text: str = Field(
        "", description="Optional partition rows: table,partition,size_gb")
    retention_days: int = Field(365, ge=1,
                                description="Partition retention window")
    llm: bool = Field(
        False, description="Also draft a governance note via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: AnalyzeRequest, resolve):
    raw = resolve(req.inventory_file, req.inventory_text,
                  "'inventory_file' or 'inventory_text'")
    return run_storage_analysis(raw, partitions_text=req.partitions_text,
                                retention_days=req.retention_days)


def _llm(req: AnalyzeRequest, result, lang: str):
    from .advisor_llm import governance_note
    from .i18n import tp

    note = governance_note(result, lang=lang)
    return ("governance_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/storagecost", tags=["storage_cost"],
    endpoint="analyze", request_model=AnalyzeRequest,
    health_name="storage_cost", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
