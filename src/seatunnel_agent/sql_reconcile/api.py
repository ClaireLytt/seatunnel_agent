# -*- coding: utf-8 -*-
"""REST API for the caliber reconciliation agent — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (deterministic — no LLM, no database, nothing executed):

  POST /api/reconcile/diff   — compare two SQL statements caliber by caliber
  GET  /api/reconcile/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .i18n import normalize_lang
from .reconciler import reconcile_sql
from .report import render_markdown, report_to_dict

router = APIRouter(prefix="/api/reconcile", tags=["sql_reconcile"])


class ReconcileRequest(BaseModel):
    sql_a: str = Field(..., description="First SQL statement")
    sql_b: str = Field(..., description="Second SQL statement")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown")


class ReconcileResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/diff", response_model=ReconcileResponse)
def diff(req: ReconcileRequest) -> ReconcileResponse:
    start = time.time()
    if not req.sql_a.strip() or not req.sql_b.strip():
        raise HTTPException(status_code=400,
                            detail="Provide BOTH sql_a and sql_b")
    lang = normalize_lang(req.lang)
    result = reconcile_sql(req.sql_a, req.sql_b, dialect=req.dialect)
    rendered = render_markdown(result, lang=lang) if req.report else None
    return ReconcileResponse(
        result=report_to_dict(result, lang=lang),
        report=rendered,
        elapsed_ms=int((time.time() - start) * 1000))


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "sql_reconcile"}
