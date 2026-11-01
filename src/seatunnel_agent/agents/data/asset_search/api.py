"""REST API for the asset searcher — FastAPI router.

  POST /api/assetsearch/search — ranked catalog matches
  GET  /api/assetsearch/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .report import render_markdown
from .searcher import parse_catalog, search_assets

_ENV = "ASSETSEARCH_API_ALLOWED_DIRS"


class SearchRequest(BaseModel):
    catalog_file: str | None = Field(
        None, description="Catalog file: JSON asset list or DDL scripts")
    catalog_text: str = Field("", description="Inline catalog")
    query: str = Field(..., description="Natural-language business need")
    limit: int = Field(10, ge=1, le=50, description="Max hits returned")
    llm: bool = Field(
        False, description="Also draft a recommendation via the "
                           "configured LLM (needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: SearchRequest, resolve):
    raw = resolve(req.catalog_file, req.catalog_text,
                  "'catalog_file' or 'catalog_text'")
    return search_assets(parse_catalog(raw), req.query, limit=req.limit)


def _llm(req: SearchRequest, result, lang: str):
    from .advisor_llm import recommend_note
    from .i18n import tp

    note = recommend_note(result, lang=lang)
    return ("recommendation", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/assetsearch", tags=["asset_search"],
    endpoint="search", request_model=SearchRequest,
    health_name="asset_search", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
