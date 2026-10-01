# -*- coding: utf-8 -*-
"""REST API for the schema drift agent — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (deterministic — no LLM, no database, nothing executed):

  POST /api/schemadrift/diff   — diff two DDL scripts or two directories
  GET  /api/schemadrift/health — health check
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .differ import diff_paths, diff_scripts
from .i18n import normalize_lang
from .report import render_markdown, report_to_dict

router = APIRouter(prefix="/api/schemadrift", tags=["schema_drift"])


def _allowed_roots() -> list[Path]:
    raw = os.getenv("SCHEMADRIFT_API_ALLOWED_DIRS", "")
    roots = [Path(p).resolve() for p in raw.split(os.pathsep) if p.strip()]
    return roots or [Path.cwd().resolve()]


def _check_path_allowed(raw_path: str) -> None:
    """API 是网络入口，路径参数必须限制在白名单内，防任意目录读取。"""
    try:
        target = Path(raw_path).resolve()
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail=f"无效路径: {raw_path}")
    if not any(
        target == root or target.is_relative_to(root)
        for root in _allowed_roots()
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                f"路径 {raw_path} 不在允许范围内。"
                "默认仅允许当前工作目录，可通过环境变量 "
                "SCHEMADRIFT_API_ALLOWED_DIRS 配置（多个目录用系统路径分隔符分隔）"
            ),
        )


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
    inline = (req.old_sql or "").strip() or (req.new_sql or "").strip()
    paths = (req.old_path or "").strip() and (req.new_path or "").strip()
    if inline:
        result = diff_scripts(req.old_sql or "", req.new_sql or "",
                              dialect=req.dialect)
    elif paths:
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
