"""REST API for the consistency-repair planner — FastAPI router.

  POST /api/datarepair/plan  — ranked repair actions with SQL templates
  GET  /api/datarepair/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .planner import plan_repairs
from .report import render_markdown

_ENV = "DATAREPAIR_API_ALLOWED_DIRS"


class PlanRequest(BaseModel):
    data_file: str | None = Field(
        None, description="CSV/JSONL data file (whitelisted dirs)")
    data_text: str = Field("", description="Inline CSV or JSONL rows")
    table: str = Field("<table>", description="Target table name for the SQL")
    pk: str = Field("", description="Primary-key column(s), comma-separated")
    biz_key: str = Field(
        "", description="Business-event key column(s), comma-separated")
    max_rows: int = Field(
        2000, ge=1, le=100_000,
        description="Profile sample cap (dup detection scans all rows)")
    llm: bool = Field(
        False, description="Also draft a repair note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: PlanRequest, resolve):
    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    return plan_repairs(raw, table=req.table or "<table>",
                        pk=req.pk or None, biz_key=req.biz_key or None,
                        max_rows=req.max_rows)


def _llm(req: PlanRequest, plan, lang: str):
    from .advisor_llm import repair_note
    from .i18n import tp

    note = repair_note(plan, lang=lang)
    return ("repair_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/datarepair", tags=["data_repair"],
    endpoint="plan", request_model=PlanRequest,
    health_name="data_repair", env_var=_ENV,
    core=_core,
    render=lambda plan, req, lang: render_markdown(plan, lang=lang),
    llm=_llm,
)
