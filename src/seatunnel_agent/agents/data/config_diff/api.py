"""REST API for the config differ — FastAPI router.

  POST /api/configdiff/diff — graded semantic differences
  GET  /api/configdiff/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .differ import diff_configs
from .report import render_markdown

_ENV = "CONFIGDIFF_API_ALLOWED_DIRS"


class DiffRequest(BaseModel):
    left_file: str | None = Field(
        None, description="Left config file (whitelisted dirs)")
    left_text: str = Field("", description="Inline left config")
    right_file: str | None = Field(
        None, description="Right config file (whitelisted dirs)")
    right_text: str = Field("", description="Inline right config")
    llm: bool = Field(
        False, description="Also draft a drift review via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: DiffRequest, resolve):
    left = resolve(req.left_file, req.left_text,
                   "'left_file' or 'left_text'")
    right = resolve(req.right_file, req.right_text,
                    "'right_file' or 'right_text'")
    return diff_configs(left, right)


def _llm(req: DiffRequest, result, lang: str):
    from .advisor_llm import drift_note
    from .i18n import tp

    note = drift_note(result, lang=lang)
    return ("drift_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/configdiff", tags=["config_diff"],
    endpoint="diff", request_model=DiffRequest,
    health_name="config_diff", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
