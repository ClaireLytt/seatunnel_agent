"""REST API for the task-failure classifier — FastAPI router.

  POST /api/taskfailure/classify — root-cause clusters with verdicts
  GET  /api/taskfailure/health   — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .classifier import classify_failures, parse_failures
from .report import render_markdown

_ENV = "TASKFAILURE_API_ALLOWED_DIRS"


class ClassifyRequest(BaseModel):
    export_file: str | None = Field(
        None, description="Failed-task export file (CSV or JSON list)")
    export_text: str = Field("", description="Inline export")
    llm: bool = Field(
        False, description="Also draft a failure note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: ClassifyRequest, resolve):
    raw = resolve(req.export_file, req.export_text,
                  "'export_file' or 'export_text'")
    return classify_failures(parse_failures(raw))


def _llm(req: ClassifyRequest, result, lang: str):
    from .advisor_llm import failure_note
    from .i18n import tp

    note = failure_note(result, lang=lang)
    return ("failure_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/taskfailure", tags=["task_failure"],
    endpoint="classify", request_model=ClassifyRequest,
    health_name="task_failure", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
