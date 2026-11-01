"""REST API for the backfill SQL agent — FastAPI router.

  POST /api/backfillsql/generate — partition-bounded backfill statements
  POST /api/backfillsql/specs    — backfill planner JSON → spec skeletons
  GET  /api/backfillsql/health   — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router
from seatunnel_agent.common.api_guard import ms_since

from .generator import generate, parse_spec
from .report import render_markdown

_ENV = "BACKFILLSQL_API_ALLOWED_DIRS"


class GenerateRequest(BaseModel):
    file: str | None = Field(None, description="Backfill spec file (.json)")
    text: str | None = Field(None, description="Inline JSON spec")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


router = make_text_router(
    prefix="/api/backfillsql", tags=["backfill_sql"],
    endpoint="generate", request_model=GenerateRequest,
    health_name="backfill_sql", env_var=_ENV,
    core=lambda req, resolve: generate(
        parse_spec(resolve(req.file, req.text, "'file' or 'text'"))),
    render=lambda result, req, lang: render_markdown(result, lang=lang),
)


class SpecsRequest(BaseModel):
    plan: str = Field(..., description="Backfill planner plan JSON")
    partition_col: str = Field("dt", description="Partition column name")
    dialect: str = Field("hive", description="Target dialect")
    ddl: str = Field("", description="Upstream CREATE TABLE DDL — with "
                                     "llm=true the source SELECT columns "
                                     "are filled in")
    llm: bool = Field(False, description="Fill each spec's source SELECT "
                                         "via the configured LLM "
                                         "(needs an API key)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")


class SpecsResponse(BaseModel):
    result: list[dict[str, Any]]
    report: str
    elapsed_ms: int


@router.post("/specs", response_model=SpecsResponse)
def run_specs(req: SpecsRequest) -> SpecsResponse:
    from .bridge import specs_from_plan
    from .report import render_specs_markdown

    start = time.time()
    if not req.plan.strip():
        raise HTTPException(status_code=400, detail="Provide 'plan'")
    try:
        specs = specs_from_plan(req.plan, partition_col=req.partition_col,
                                dialect=req.dialect)
    except Exception as exc:  # bad input, malformed JSON
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    warnings: list[str] = []
    if req.llm:
        from . import advisor_llm

        try:
            warnings = advisor_llm.fill_specs(specs, req.ddl,
                                              lang=req.lang)
        except Exception as exc:  # missing key, provider errors
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    report = render_specs_markdown(specs, lang=req.lang, warnings=warnings)
    return SpecsResponse(result=specs, report=report,
                         elapsed_ms=ms_since(start))
