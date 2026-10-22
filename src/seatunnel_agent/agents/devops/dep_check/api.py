"""REST API for dependency health — FastAPI router.

  POST /api/depcheck/check      — check inline pyproject/requirements text
  GET  /api/depcheck/check-self  — check this server's own project deps
  GET  /api/depcheck/health      — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since

from .core import (
    check,
    collect_from_path,
    parse_pyproject_text,
    parse_requirements_text,
)
from .report import normalize_lang, render_markdown

router = APIRouter(prefix="/api/depcheck", tags=["dep_check"])


class CheckRequest(BaseModel):
    pyproject_text: str = Field("", description="pyproject.toml content")
    requirements_text: str = Field("", description="requirements.txt content")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the markdown report")


class CheckResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/check", response_model=CheckResponse)
def check_deps(req: CheckRequest) -> CheckResponse:
    start = time.time()
    if not req.pyproject_text.strip() and not req.requirements_text.strip():
        raise HTTPException(status_code=400,
                            detail="Provide pyproject_text or requirements_text")
    try:
        reqs = (parse_pyproject_text(req.pyproject_text)
                if req.pyproject_text.strip() else [])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    reqs += parse_requirements_text(req.requirements_text)
    result = check(reqs)
    return CheckResponse(
        result=result.to_dict(),
        report=(render_markdown(result, normalize_lang(req.lang))
                if req.report else None),
        elapsed_ms=ms_since(start),
    )


@router.get("/check-self", response_model=CheckResponse)
def check_self(lang: str = "zh") -> CheckResponse:
    """Check the server's own project dependencies."""
    start = time.time()
    reqs = collect_from_path(".")
    result = check(reqs)
    return CheckResponse(
        result=result.to_dict(),
        report=render_markdown(result, normalize_lang(lang)),
        elapsed_ms=ms_since(start),
    )


add_health(router, "dep_check")
