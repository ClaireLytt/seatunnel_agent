"""REST API for the topic-schema differ — FastAPI router.

  POST /api/topicschema/diff — graded compatibility findings
  GET  /api/topicschema/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .differ import diff_topic_schemas
from .report import render_markdown

_ENV = "TOPICSCHEMA_API_ALLOWED_DIRS"


class DiffRequest(BaseModel):
    old_file: str | None = Field(
        None, description="Old schema JSON file (whitelisted dirs)")
    old_text: str = Field("", description="Inline old Avro/JSON Schema")
    new_file: str | None = Field(
        None, description="New schema JSON file (whitelisted dirs)")
    new_text: str = Field("", description="Inline new Avro/JSON Schema")
    mode: str = Field("backward", description="Compatibility mode: "
                                              "backward|forward|full")
    llm: bool = Field(
        False, description="Also draft a rollout note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: DiffRequest, resolve):
    old = resolve(req.old_file, req.old_text, "'old_file' or 'old_text'")
    new = resolve(req.new_file, req.new_text, "'new_file' or 'new_text'")
    return diff_topic_schemas(old, new, mode=req.mode)


def _llm(req: DiffRequest, result, lang: str):
    from .advisor_llm import rollout_note
    from .i18n import tp

    note = rollout_note(result, lang=lang)
    return ("rollout_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/topicschema", tags=["topic_schema"],
    endpoint="diff", request_model=DiffRequest,
    health_name="topic_schema", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
