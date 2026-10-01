# -*- coding: utf-8 -*-
"""REST API for the SQL transpile agent — FastAPI router.

Mount on the Gradio app's FastAPI instance to serve alongside the UI.
Endpoints (all deterministic — no LLM, no SQL execution):
  POST /api/transpile/translate — translate a SQL script
  POST /api/transpile/batch     — analyze every *.sql under a directory (read-only)
  GET  /api/transpile/dialects  — supported dialect matrix
  GET  /api/transpile/health    — health check
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .i18n import normalize_lang
from .report import batch_to_dict, render_markdown, result_to_dict
from .transpiler import DIALECTS, translate, transpile_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/transpile", tags=["transpile"])

_DIALECT_DESC = " | ".join(DIALECTS)


def _check_dir_allowed(raw_dir: str) -> None:
    """API 是网络入口，目录参数必须限制在白名单内，防任意目录扫描。"""
    from ..api_guard import check_path_allowed

    check_path_allowed(raw_dir, "TRANSPILE_API_ALLOWED_DIRS")


class TranslateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sql: str = Field(..., min_length=1, description="SQL script to translate")
    to: str = Field(..., description=f"Target dialect: {_DIALECT_DESC}")
    from_dialect: str | None = Field(
        None, alias="from",
        description=f"Source dialect (inferred when omitted): {_DIALECT_DESC}")
    lang: str = Field("zh", description="Message language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class BatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    dir: str = Field(..., min_length=1,
                     description="Directory scanned recursively for *.sql")
    to: str = Field(..., description=f"Target dialect: {_DIALECT_DESC}")
    from_dialect: str | None = Field(None, alias="from")
    lang: str = Field("zh", description="Message language: 'zh' or 'en'")


@router.post("/translate")
def translate_endpoint(req: TranslateRequest) -> dict[str, Any]:
    lang = normalize_lang(req.lang)
    try:
        result = translate(req.sql, dst=req.to, src=req.from_dialect)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    data = result_to_dict(result, lang)
    data["output_sql"] = result.output_script()
    if req.report:
        data["report"] = render_markdown(result, lang)
    logger.info("transpile %s→%s: %s", result.src_dialect,
                result.dst_dialect, data["stats"])
    return data


@router.post("/batch")
def batch_endpoint(req: BatchRequest) -> dict[str, Any]:
    """Analyze-only: the API never writes translated files to disk."""
    _check_dir_allowed(req.dir)
    if not Path(req.dir).is_dir():
        raise HTTPException(status_code=400, detail=f"目录不存在: {req.dir}")
    try:
        batch = transpile_dir(req.dir, dst=req.to, src=req.from_dialect)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return batch_to_dict(batch, normalize_lang(req.lang))


@router.get("/dialects")
def dialects_endpoint() -> dict[str, Any]:
    return {"dialects": list(DIALECTS), "sources": list(DIALECTS),
            "targets": list(DIALECTS)}


@router.get("/health")
def health_endpoint() -> dict[str, str]:
    return {"status": "ok"}
