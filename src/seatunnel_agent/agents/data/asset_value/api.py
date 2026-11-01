"""REST API for the asset-value grader — FastAPI router.

  POST /api/assetvalue/grade  — scored tiers and quadrants
  GET  /api/assetvalue/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .report import render_markdown
from .valuer import parse_inventory, value_assets

_ENV = "ASSETVALUE_API_ALLOWED_DIRS"


class GradeRequest(BaseModel):
    inventory_file: str | None = Field(
        None, description="Inventory file: CSV or JSON asset rows")
    inventory_text: str = Field("", description="Inline inventory rows")
    llm: bool = Field(
        False, description="Also draft a grading note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: GradeRequest, resolve):
    raw = resolve(req.inventory_file, req.inventory_text,
                  "'inventory_file' or 'inventory_text'")
    return value_assets(parse_inventory(raw))


def _llm(req: GradeRequest, result, lang: str):
    from .advisor_llm import grading_note
    from .i18n import tp

    note = grading_note(result, lang=lang)
    return ("grading_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/assetvalue", tags=["asset_value"],
    endpoint="grade", request_model=GradeRequest,
    health_name="asset_value", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
