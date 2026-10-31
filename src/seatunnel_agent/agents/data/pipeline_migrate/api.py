"""REST API for the migration assessor agent — FastAPI router.

  POST /api/pipemigrate/assess — per-job target, effort and risks
  GET  /api/pipemigrate/health — health check
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router
from seatunnel_agent.common.api_guard import require_dir

from .assessor import assess_dir, assess_text
from .report import render_markdown

_ENV = "PIPEMIGRATE_API_ALLOWED_DIRS"


class AssessRequest(BaseModel):
    dir: str | None = Field(
        None, description="Legacy scripts directory (recursive)")
    text: str | None = Field(None, description="One inline script")
    name: str = Field("pasted.sql", description="Name for the inline script")
    llm: bool = Field(
        False, description="Also ask the configured LLM for rewrite advice "
                           "on the riskiest jobs (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: AssessRequest, resolve):
    if not (req.dir or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'dir' or 'text'")
    if (req.dir or "").strip():
        return assess_dir(require_dir(req.dir or "", _ENV))
    return assess_text(req.name, req.text or "")


def _llm(req: AssessRequest, result, lang: str):
    from . import advisor_llm

    scripts = advisor_llm.collect_scripts(
        result.jobs, root=(req.dir or "").strip() or None,
        fallback=(req.name, req.text or ""))
    advice = advisor_llm.advice_for_jobs(result.jobs, scripts, lang=lang)
    section = advisor_llm.render_advice(advice, lang) if advice else ""
    return ("llm_advice",
            [{"job": j, "advice": a} for j, a in advice], section)


router = make_text_router(
    prefix="/api/pipemigrate", tags=["pipeline_migrate"],
    endpoint="assess", request_model=AssessRequest,
    health_name="pipeline_migrate", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
