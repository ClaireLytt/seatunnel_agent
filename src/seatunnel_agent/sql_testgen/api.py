# -*- coding: utf-8 -*-
"""REST API for the SQL test-data generator — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Everything is returned inline (CSV text, INSERT/CREATE statements) — the
API never writes to the filesystem, so no directory whitelist is needed.

  POST /api/testgen/generate — generate datasets for a query
  GET  /api/testgen/health   — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .generator import DEFAULT_ROWS, MAX_ROWS, generate
from .i18n import normalize_lang
from .report import render_markdown, result_to_dict
from .validator import validate_with_sqlite

router = APIRouter(prefix="/api/testgen", tags=["sql_testgen"])


class TestgenRequest(BaseModel):
    sql: str = Field(..., min_length=1, description="Query to generate data for")
    ddl: str = Field("", description="Optional CREATE TABLE script for exact types")
    rows: int = Field(DEFAULT_ROWS, ge=1, le=MAX_ROWS,
                      description="Rows per table")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    validate_sqlite: bool = Field(
        True, description="Execute data + query on in-memory SQLite")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class TestgenResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/generate", response_model=TestgenResponse)
def generate_data(req: TestgenRequest) -> TestgenResponse:
    start = time.time()
    lang = normalize_lang(req.lang)
    result = generate(req.sql, ddl=req.ddl, rows=req.rows,
                      dialect=req.dialect)
    if not result.tables and result.warnings:
        raise HTTPException(status_code=400,
                            detail="; ".join(result.warnings))
    if req.validate_sqlite:
        result.validation = validate_with_sqlite(result)
    return TestgenResponse(
        result=result_to_dict(result),
        report=render_markdown(result, lang) if req.report else None,
        elapsed_ms=int((time.time() - start) * 1000),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "sql_testgen"}
