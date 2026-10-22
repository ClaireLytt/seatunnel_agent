"""REST API for the release-notes helper — FastAPI router.

  POST /api/release/notes      — build grouped notes + version suggestion
  GET  /api/release/git-log    — collect git log from the server's repo
  GET  /api/release/health     — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since

from .core import build_notes, collect_git_log
from .report import normalize_lang, polish_markdown, render_markdown

router = APIRouter(prefix="/api/release", tags=["release_notes"])


class NotesRequest(BaseModel):
    log_text: str = Field(..., min_length=1,
                          description="sha<TAB>subject per line")
    current_version: str = Field("", description="e.g. 0.2.0")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the markdown report")
    polish: bool = Field(False, description="Apply LLM polish to the report")


class NotesResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/notes", response_model=NotesResponse)
def notes(req: NotesRequest) -> NotesResponse:
    start = time.time()
    result = build_notes(req.log_text, req.current_version)
    lang = normalize_lang(req.lang)
    report: str | None = None
    if req.report:
        report = render_markdown(result, lang)
        if req.polish:
            report = polish_markdown(report, lang)
    return NotesResponse(
        result=result.to_dict(),
        report=report,
        elapsed_ms=ms_since(start),
    )


class GitLogResponse(BaseModel):
    log_text: str
    elapsed_ms: int


@router.get("/git-log", response_model=GitLogResponse)
def git_log(lang: str = "zh") -> GitLogResponse:
    """Collect git log from the server's own repository."""
    start = time.time()
    text = collect_git_log(".")
    return GitLogResponse(log_text=text, elapsed_ms=ms_since(start))


add_health(router, "release_notes")
