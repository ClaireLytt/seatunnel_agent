"""REST API for the Kafka-lag analyzer — FastAPI router.

  POST /api/kafkalag/diagnose — ranked lag findings
  GET  /api/kafkalag/health   — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .analyzer import analyze_lag, parse_lag_snapshot
from .report import render_markdown

_ENV = "KAFKALAG_API_ALLOWED_DIRS"


class DiagnoseRequest(BaseModel):
    snapshot_file: str | None = Field(
        None, description="Consumer-group snapshot file (JSON or CSV)")
    snapshot_text: str = Field("", description="Inline snapshot")
    llm: bool = Field(
        False, description="Also draft an ops note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: DiagnoseRequest, resolve):
    raw = resolve(req.snapshot_file, req.snapshot_text,
                  "'snapshot_file' or 'snapshot_text'")
    group, parts = parse_lag_snapshot(raw)
    return analyze_lag(group, parts)


def _llm(req: DiagnoseRequest, result, lang: str):
    from .advisor_llm import ops_note
    from .i18n import tp

    note = ops_note(result, lang=lang)
    return ("ops_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/kafkalag", tags=["kafka_lag"],
    endpoint="diagnose", request_model=DiagnoseRequest,
    health_name="kafka_lag", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
