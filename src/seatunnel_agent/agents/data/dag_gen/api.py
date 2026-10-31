"""REST API for the DAG drafter — FastAPI router.

  POST /api/daggen/generate — importable Airflow DAG skeleton
  GET  /api/daggen/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .generator import generate_dag
from .report import render_markdown

_ENV = "DAGGEN_API_ALLOWED_DIRS"


class GenerateRequest(BaseModel):
    sql_file: str | None = Field(
        None, description="Pipeline SQL file (whitelisted dirs)")
    sql_text: str = Field("", description="Inline pipeline SQL scripts")
    dag_id: str = Field("pipeline", description="Airflow dag_id "
                                                "(identifier)")
    schedule: str = Field("0 2 * * *", description="Cron schedule")
    dialect: str = Field("hive", description="SQL dialect for the parser")
    llm: bool = Field(
        False, description="Also draft a pre-deploy review via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: GenerateRequest, resolve):
    raw = resolve(req.sql_file, req.sql_text, "'sql_file' or 'sql_text'")
    return generate_dag(raw, dag_id=req.dag_id, schedule=req.schedule,
                        dialect=req.dialect)


def _llm(req: GenerateRequest, result, lang: str):
    from .advisor_llm import schedule_note
    from .i18n import tp

    note = schedule_note(result, lang=lang)
    return ("schedule_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/daggen", tags=["dag_gen"],
    endpoint="generate", request_model=GenerateRequest,
    health_name="dag_gen", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
