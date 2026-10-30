"""REST API for the backfill SQL agent — FastAPI router.

  POST /api/backfillsql/generate — partition-bounded backfill statements
  POST /api/backfillsql/specs    — backfill planner JSON → spec skeletons
  GET  /api/backfillsql/health   — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import (
    add_health,
    ms_since,
    read_whitelisted_file,
)
from seatunnel_agent.common.utils import normalize_lang

from .generator import generate, parse_spec
from .report import render_markdown

router = APIRouter(prefix="/api/backfillsql", tags=["backfill_sql"])

_ENV = "BACKFILLSQL_API_ALLOWED_DIRS"


class GenerateRequest(BaseModel):
    file: str | None = Field(None, description="Backfill spec file (.json)")
    text: str | None = Field(None, description="Inline JSON spec")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class GenerateResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int



@router.post("/generate", response_model=GenerateResponse)
def run_generate(req: GenerateRequest) -> GenerateResponse:
    start = time.time()
    if not (req.file or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'file' or 'text'")
    text = (read_whitelisted_file(req.file or "", _ENV) if (req.file or "").strip()
            else req.text or "")
    try:
        result = generate(parse_spec(text))
    except Exception as exc:  # bad input, malformed JSON
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    lang = normalize_lang(req.lang)
    report = render_markdown(result, lang=lang) if req.report else None
    return GenerateResponse(result=result.to_dict(), report=report,
                            elapsed_ms=ms_since(start))


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


add_health(router, "backfill_sql")
