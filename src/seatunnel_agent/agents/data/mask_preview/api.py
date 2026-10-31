"""REST API for the mask previewer — FastAPI router.

  POST /api/maskpreview/preview — masking rules + masked rows
  GET  /api/maskpreview/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .masker import preview_mask
from .report import render_markdown

_ENV = "MASKPREVIEW_API_ALLOWED_DIRS"


class PreviewRequest(BaseModel):
    data_file: str | None = Field(
        None, description="CSV/JSONL data file (whitelisted dirs)")
    data_text: str = Field("", description="Inline CSV (header row) or "
                                           "JSONL rows")
    preview_rows: int = Field(20, description="Masked rows shown in the "
                                              "preview")
    llm: bool = Field(
        False, description="Also draft a policy note via the configured "
                           "LLM (needs an API key; rule metadata only, "
                           "never the rows)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: PreviewRequest, resolve):
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    headers, rows = parse_rows(raw)
    return preview_mask(headers, rows, preview_rows=req.preview_rows)


def _llm(req: PreviewRequest, result, lang: str):
    from .advisor_llm import policy_note
    from .i18n import tp

    note = policy_note(result, lang=lang)
    return ("policy_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/maskpreview", tags=["mask_preview"],
    endpoint="preview", request_model=PreviewRequest,
    health_name="mask_preview", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
