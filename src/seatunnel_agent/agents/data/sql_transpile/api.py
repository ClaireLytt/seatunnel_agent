"""REST API for the SQL transpile agent — FastAPI router.

Mount on the Gradio app's FastAPI instance to serve alongside the UI.
Endpoints (deterministic unless stated — no SQL execution):
  POST /api/transpile/translate — translate a SQL script
  POST /api/transpile/batch     — analyze every *.sql under a directory;
                                  optional whitelist-guarded out_dir write-out
  POST /api/transpile/advice    — optional LLM advice over a translate result
  GET  /api/transpile/dialects  — supported dialect matrix
  GET  /api/transpile/health    — health check
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from seatunnel_agent.common.utils import normalize_lang

from .report import batch_to_dict, render_markdown, result_to_dict
from .transpiler import DIALECTS, translate, transpile_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/transpile", tags=["transpile"])

_DIALECT_DESC = " | ".join(DIALECTS)


def _check_dir_allowed(raw_dir: str) -> None:
    """API 是网络入口，目录参数必须限制在白名单内，防任意目录扫描。"""
    from seatunnel_agent.common.api_guard import check_path_allowed

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
    out_dir: str | None = Field(
        None, description="Write translated files mirroring the input tree "
                          "(whitelist-guarded like 'dir')")


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
    """Analyze by default; writes only into a whitelist-guarded out_dir."""
    _check_dir_allowed(req.dir)
    if not Path(req.dir).is_dir():
        # structured detail: the frontend localizes it (i18n `bad_dir`)
        raise HTTPException(status_code=400,
                            detail={"code": "bad_dir", "path": req.dir})
    out_dir = (req.out_dir or "").strip() or None
    if out_dir:
        _check_dir_allowed(out_dir)  # write target under the same whitelist
    try:
        batch = transpile_dir(req.dir, dst=req.to, src=req.from_dialect,
                              out_dir=out_dir)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return batch_to_dict(batch, normalize_lang(req.lang))


class AdviceRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sql: str = Field(..., min_length=1, description="SQL script to advise on")
    to: str = Field(..., description=f"Target dialect: {_DIALECT_DESC}")
    from_dialect: str | None = Field(None, alias="from")
    lang: str = Field("zh", description="Message language: 'zh' or 'en'")


@router.post("/advice")
def advice_endpoint(req: AdviceRequest) -> dict[str, Any]:
    """Optional LLM advice — thin wrapper over the UI/CLI advisor path.

    Status values the frontend localizes: 'none' (nothing advisable),
    'no_key' (LLM unconfigured), 'ok' (advice markdown returned),
    'error' (LLM call failed — detail carries the message, never a 500).
    """
    from .advisor import advisable_issues, generate_advice

    lang = normalize_lang(req.lang)
    try:
        result = translate(req.sql, dst=req.to, src=req.from_dialect)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not advisable_issues(result):
        return {"status": "none", "advice": None}
    try:
        from seatunnel_agent.common.config import load_settings
        settings = load_settings()
    except RuntimeError:
        return {"status": "no_key", "advice": None}
    try:
        advice = generate_advice(settings, result, lang)
    except Exception as exc:  # LLM/transport failure — mirror the legacy
        logger.warning("transpile advice failed: %s", exc)  # UI's ⚠️ path
        return {"status": "error", "advice": None,
                "detail": f"{type(exc).__name__}: {exc}"}
    if not advice:
        return {"status": "none", "advice": None}
    return {"status": "ok", "advice": advice}


@router.get("/dialects")
def dialects_endpoint() -> dict[str, Any]:
    return {"dialects": list(DIALECTS), "sources": list(DIALECTS),
            "targets": list(DIALECTS)}


@router.get("/health")
def health_endpoint() -> dict[str, str]:
    return {"status": "ok"}
