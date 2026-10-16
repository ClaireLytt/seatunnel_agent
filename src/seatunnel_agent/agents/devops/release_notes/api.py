"""REST API for the release-notes helper — FastAPI router.

Inline commit-log text only (``sha<TAB>subject`` per line) — the API never
runs git or reads repo paths.  LLM polish is a CLI/UI affair.

  POST /api/release/notes  — build grouped notes + version suggestion
  GET  /api/release/health — health check
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since

from .core import build_notes
from .report import normalize_lang, render_markdown

router = APIRouter(prefix="/api/release", tags=["release_notes"])


class NotesRequest(BaseModel):
    log_text: str = Field(..., min_length=1,
                          description="sha<TAB>subject per line")
    current_version: str = Field("", description="e.g. 0.2.0")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the markdown report")


class NotesResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/notes", response_model=NotesResponse)
def notes(req: NotesRequest) -> NotesResponse:
    start = time.time()
    result = build_notes(req.log_text, req.current_version)
    return NotesResponse(
        result=result.to_dict(),
        report=(render_markdown(result, normalize_lang(req.lang))
                if req.report else None),
        elapsed_ms=ms_since(start),
    )


add_health(router, "release_notes")
