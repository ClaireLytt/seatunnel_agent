# -*- coding: utf-8 -*-
"""REST API for the SQL formatter — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Inline only — the API never writes to the filesystem (``--write`` is a CLI
affair), so no directory whitelist is needed.

  POST /api/sqlfmt/format — format a SQL script
  GET  /api/sqlfmt/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .formatter import format_text
from .i18n import normalize_lang
from .report import render_markdown, result_to_dict

router = APIRouter(prefix="/api/sqlfmt", tags=["sql_fmt"])


class FormatRequest(BaseModel):
    sql: str = Field(..., min_length=1, description="SQL script to format")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class FormatResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/format", response_model=FormatResponse)
def format_sql(req: FormatRequest) -> FormatResponse:
    start = time.time()
    lang = normalize_lang(req.lang)
    result = format_text(req.sql, dialect=req.dialect)
    return FormatResponse(
        result=result_to_dict(result),
        report=render_markdown(result, lang) if req.report else None,
        elapsed_ms=int((time.time() - start) * 1000),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "sql_fmt"}
