"""REST API for the SLA trace agent — FastAPI router.

  POST /api/slatrace/trace  — critical path + delay attribution
  GET  /api/slatrace/health — health check
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from seatunnel_agent.common.api_guard import add_health, ms_since, require_dir
from seatunnel_agent.common.utils import normalize_lang

from .report import render_markdown, trace_to_dict
from .tracer import parse_instances, trace

router = APIRouter(prefix="/api/slatrace", tags=["sla_trace"])


class TraceRequest(BaseModel):
    file: str | None = Field(
        None, description="Task-instance export file (.json/.csv)")
    text: str | None = Field(None, description="Inline JSON/CSV export")
    target: str = Field("", description="Target task (default: last to end)")
    deadline: str | None = Field(
        None, description="SLA deadline, ISO timestamp")
    top: int = Field(5, ge=1, le=50, description="Top delay contributors")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


class TraceResponse(BaseModel):
    result: dict[str, Any]
    report: str | None = None
    elapsed_ms: int


@router.post("/trace", response_model=TraceResponse)
def run_trace(req: TraceRequest) -> TraceResponse:
    start = time.time()
    if not (req.file or "").strip() and not (req.text or "").strip():
        raise HTTPException(status_code=400, detail="Provide 'file' or 'text'")
    if (req.file or "").strip():
        path = Path(req.file.strip())
        require_dir(str(path.parent), "SLATRACE_API_ALLOWED_DIRS")
        if not path.is_file():
            raise HTTPException(status_code=400,
                                detail=f"Not a file: {path}")
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        text = req.text or ""
    try:
        result = trace(parse_instances(text), target=req.target.strip(),
                       deadline=(req.deadline or "").strip() or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    lang = normalize_lang(req.lang)
    return TraceResponse(
        result=trace_to_dict(result),
        report=(render_markdown(result, lang, top=req.top)
                if req.report else None),
        elapsed_ms=ms_since(start),
    )


add_health(router, "sla_trace")
