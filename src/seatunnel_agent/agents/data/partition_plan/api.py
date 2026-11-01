"""REST API for the partition planner — FastAPI router.

  POST /api/partitionplan/plan — ranked candidates + DDL clauses
  GET  /api/partitionplan/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .planner import plan_partitions
from .report import render_markdown

_ENV = "PARTITIONPLAN_API_ALLOWED_DIRS"


class PlanRequest(BaseModel):
    data_file: str | None = Field(
        None, description="Sample CSV/JSONL file (whitelisted dirs)")
    data_text: str = Field("", description="Inline sample rows")
    queries_file: str | None = Field(
        None, description="Query workload SQL file (whitelisted dirs)")
    queries_text: str = Field("", description="Inline query workload")
    dialect: str = Field("hive", description="SQL dialect for the parser")
    llm: bool = Field(
        False, description="Also draft a pre-DDL review via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: PlanRequest, resolve):
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    queries = resolve(req.queries_file, req.queries_text,
                      "'queries_file' or 'queries_text'")
    headers, rows = parse_rows(raw)
    return plan_partitions(headers, rows, queries, dialect=req.dialect)


def _llm(req: PlanRequest, result, lang: str):
    from .advisor_llm import plan_note
    from .i18n import tp

    note = plan_note(result, lang=lang)
    return ("plan_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/partitionplan", tags=["partition_plan"],
    endpoint="plan", request_model=PlanRequest,
    health_name="partition_plan", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
