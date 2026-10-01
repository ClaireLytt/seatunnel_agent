# -*- coding: utf-8 -*-
"""REST API for the schema drift agent — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (deterministic — no LLM, no database, nothing executed):

  POST /api/schemadrift/diff   — diff two DDL scripts or two directories
  GET  /api/schemadrift/health — health check
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..api_guard import check_path_allowed
from .differ import diff_paths, diff_scripts
from .i18n import normalize_lang
from .report import render_markdown, report_to_dict

router = APIRouter(prefix="/api/schemadrift", tags=["schema_drift"])


def _check_path_allowed(raw_path: str) -> None:
    """API 是网络入口，路径参数必须限制在白名单内，防任意目录读取。"""
    check_path_allowed(raw_path, "SCHEMADRIFT_API_ALLOWED_DIRS", noun="路径")


class DriftRequest(BaseModel):
    old_sql: str | None = Field(None, description="Old DDL script (inline)")
    new_sql: str | None = Field(None, description="New DDL script (inline)")
    old_path: str | None = Field(None, description="Old DDL file/directory")
    new_path: str | None = Field(None, description="New DDL file/directory")
    dialect: str = Field("hive", description="SQL dialect for parsing")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class DriftResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/diff", response_model=DriftResponse)
def diff(req: DriftRequest) -> DriftResponse:
    start = time.time()
    lang = normalize_lang(req.lang)
    has_old_sql = bool((req.old_sql or "").strip())
    has_new_sql = bool((req.new_sql or "").strip())
    has_old_path = bool((req.old_path or "").strip())
    has_new_path = bool((req.new_path or "").strip())
    # Reject half-filled or mixed input: diffing one script against an
    # implicit empty one reports every table as removed — a plausible-looking
    # but meaningless result from a caller mistake.
    if has_old_sql != has_new_sql or has_old_path != has_new_path:
        raise HTTPException(
            status_code=400,
            detail="Provide BOTH old_sql and new_sql, or BOTH old_path and new_path")
    if has_old_sql and has_old_path:
        raise HTTPException(
            status_code=400,
            detail="Provide either inline SQL or paths, not both")
    if has_old_sql:
        result = diff_scripts(req.old_sql, req.new_sql, dialect=req.dialect)
    elif has_old_path:
        for raw in (req.old_path.strip(), req.new_path.strip()):
            _check_path_allowed(raw)
            if not Path(raw).exists():
                raise HTTPException(status_code=400,
                                    detail=f"路径不存在: {raw}")
        result = diff_paths(req.old_path.strip(), req.new_path.strip(),
                            dialect=req.dialect)
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide old_sql/new_sql or old_path/new_path")
    return DriftResponse(
        result=report_to_dict(result, lang),
        report=render_markdown(result, lang) if req.report else None,
        elapsed_ms=int((time.time() - start) * 1000),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "schema_drift"}
