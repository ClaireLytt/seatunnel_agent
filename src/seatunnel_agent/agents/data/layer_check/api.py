"""REST API for the layering checker — FastAPI router.

  POST /api/layercheck/check — layering violations over the SQL lineage
  GET  /api/layercheck/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .checker import parse_layer_map, run_layer_check
from .report import render_markdown

_ENV = "LAYERCHECK_API_ALLOWED_DIRS"


class CheckRequest(BaseModel):
    sql_file: str | None = Field(
        None, description="Pipeline SQL file (whitelisted dirs)")
    sql_text: str = Field("", description="Inline pipeline SQL scripts")
    dialect: str = Field("hive", description="SQL dialect for the parser")
    layers_text: str = Field(
        "", description="Optional custom layer map JSON {prefix: rank} — "
                        "replaces the built-in")
    llm: bool = Field(
        False, description="Also draft a layering note via the configured "
                           "LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: CheckRequest, resolve):
    raw = resolve(req.sql_file, req.sql_text, "'sql_file' or 'sql_text'")
    layers = (parse_layer_map(req.layers_text)
              if req.layers_text.strip() else None)
    return run_layer_check(raw, dialect=req.dialect, layers=layers)


def _llm(req: CheckRequest, result, lang: str):
    from .advisor_llm import layering_note
    from .i18n import tp

    note = layering_note(result, lang=lang)
    return ("layering_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/layercheck", tags=["layer_check"],
    endpoint="check", request_model=CheckRequest,
    health_name="layer_check", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
