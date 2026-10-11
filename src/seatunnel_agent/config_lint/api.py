# -*- coding: utf-8 -*-
"""REST API for the config lint agent — FastAPI router.

Mount on the Gradio app's FastAPI instance (``seatunnel-agent ui --api``).
Endpoints (deterministic — configs parsed, never executed):

  POST /api/conflint/lint   — lint inline HOCON or a whitelisted directory
  GET  /api/conflint/health — health check
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..api_guard import check_path_allowed
from .i18n import normalize_lang
from .linter import lint_dir, lint_text
from .report import render_batch_markdown, render_markdown, result_to_dict

router = APIRouter(prefix="/api/conflint", tags=["config_lint"])


class LintRequest(BaseModel):
    config: str | None = Field(None, description="Inline HOCON config text")
    dir: str | None = Field(None, description="Directory scanned recursively for *.conf")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class LintResponse(BaseModel):
    results: list[dict[str, Any]]
    report: str | None = None
    elapsed_ms: int


@router.post("/lint", response_model=LintResponse)
def lint(req: LintRequest) -> LintResponse:
    start = time.time()
    if not (req.config or "").strip() and not (req.dir or "").strip():
        raise HTTPException(status_code=400,
                            detail="Provide 'config' or 'dir'")
    lang = normalize_lang(req.lang)
    if (req.dir or "").strip():
        target = req.dir.strip()
        check_path_allowed(target, "CONFLINT_API_ALLOWED_DIRS")
        if not Path(target).is_dir():
            raise HTTPException(status_code=400,
                                detail=f"不是有效目录: {target}")
        results = lint_dir(target)
        report = render_batch_markdown(results, lang) if req.report else None
    else:
        results = [lint_text(req.config)]
        report = render_markdown(results[0], lang) if req.report else None
    return LintResponse(
        results=[result_to_dict(r, lang) for r in results],
        report=report,
        elapsed_ms=int((time.time() - start) * 1000),
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "config_lint"}
