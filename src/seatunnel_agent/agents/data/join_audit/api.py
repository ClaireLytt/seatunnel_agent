"""REST API for the join auditor — FastAPI router.

  POST /api/joinaudit/audit — join-quality metrics + graded findings
  GET  /api/joinaudit/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .auditor import audit_join, parse_keys
from .report import render_markdown

_ENV = "JOINAUDIT_API_ALLOWED_DIRS"


class AuditRequest(BaseModel):
    left_file: str | None = Field(
        None, description="Left-side CSV/JSONL file (whitelisted dirs)")
    left_text: str = Field("", description="Inline left rows")
    right_file: str | None = Field(
        None, description="Right-side CSV/JSONL file (whitelisted dirs)")
    right_text: str = Field("", description="Inline right rows")
    keys: str = Field(..., description="Join keys: 'k', 'lk=rk', comma "
                                       "to combine")
    llm: bool = Field(
        False, description="Also draft a join review via the configured "
                           "LLM (needs an API key; metrics only, never "
                           "the rows)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: AuditRequest, resolve):
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    left = resolve(req.left_file, req.left_text,
                   "'left_file' or 'left_text'")
    right = resolve(req.right_file, req.right_text,
                    "'right_file' or 'right_text'")
    lh, lrows = parse_rows(left)
    rh, rrows = parse_rows(right)
    return audit_join(lh, lrows, rh, rrows, parse_keys(req.keys))


def _llm(req: AuditRequest, result, lang: str):
    from .advisor_llm import join_note
    from .i18n import tp

    note = join_note(result, lang=lang)
    return ("join_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/joinaudit", tags=["join_audit"],
    endpoint="audit", request_model=AuditRequest,
    health_name="join_audit", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
